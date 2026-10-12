import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.knowledge_entry import KnowledgeCategory, KnowledgeEntry, KnowledgeEntryStatus
from app.models.membership import MembershipRole
from app.schemas.knowledge import (
    KnowledgeEntryCreate,
    KnowledgeEntryPublic,
    KnowledgeEntryUpdate,
    KnowledgeListResponse,
)
from app.services.activity_service import ActivityService

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
KNOWLEDGE_LIST_MAX = 200
AI_CONTEXT_CHAR_BUDGET = 6000
AI_CONTEXT_MAX_ENTRIES = 8
_AI_CANDIDATE_LIMIT = 200
_WORD = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "you", "your", "are", "with", "that", "this", "have",
        "can", "our", "from", "what", "how", "about", "would", "like", "please",
        "will", "not", "but", "all", "any", "was", "were", "has", "had", "its",
    }
)  # fmt: skip


_CATEGORY_LABELS = {
    KnowledgeCategory.FAQ: "FAQ",
    KnowledgeCategory.PRODUCT: "Product",
    KnowledgeCategory.POLICY: "Policy",
    KnowledgeCategory.COMPANY: "Company",
    KnowledgeCategory.OTHER: "Other",
}


def _require_manager(role: str) -> None:
    try:
        parsed = MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError("Not allowed to manage knowledge") from exc
    if parsed not in MANAGER_ROLES:
        raise ForbiddenError("Not allowed to manage knowledge")


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_", "\\"})
    return cleaned or None


def _words(value: str) -> set[str]:
    return {word for word in _WORD.findall(value.lower()) if word not in _STOPWORDS}


class KnowledgeService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_entries(
        self,
        organization_id: str,
        *,
        category: KnowledgeCategory | None = None,
        status: KnowledgeEntryStatus | None = KnowledgeEntryStatus.ACTIVE,
        search: str | None = None,
    ) -> KnowledgeListResponse:
        conditions = [KnowledgeEntry.organization_id == organization_id]
        if status is not None:
            conditions.append(KnowledgeEntry.status == status)
        term = _sanitize_search(search)
        if term:
            pattern = f"%{term.lower()}%"
            conditions.append(
                or_(
                    func.lower(KnowledgeEntry.title).like(pattern),
                    func.lower(KnowledgeEntry.content).like(pattern),
                )
            )
        category_counts: Counter[str] = Counter(
            {
                str(value): int(count)
                for value, count in self.session.execute(
                    select(KnowledgeEntry.category, func.count())
                    .where(*conditions)
                    .group_by(KnowledgeEntry.category)
                )
            }
        )
        if category is not None:
            conditions.append(KnowledgeEntry.category == category)
        rows = self.session.scalars(
            select(KnowledgeEntry)
            .where(*conditions)
            .order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.id)
            .limit(KNOWLEDGE_LIST_MAX)
        ).all()
        total = int(
            self.session.scalar(select(func.count()).select_from(KnowledgeEntry).where(*conditions))
            or 0
        )
        return KnowledgeListResponse(
            items=[KnowledgeEntryPublic.model_validate(row) for row in rows],
            total=total,
            category_counts={item: category_counts[item.value] for item in KnowledgeCategory},
        )

    def get(self, organization_id: str, entry_id: str) -> KnowledgeEntry:
        row = self.session.scalar(
            select(KnowledgeEntry).where(
                KnowledgeEntry.organization_id == organization_id,
                KnowledgeEntry.id == entry_id,
            )
        )
        if row is None:
            raise NotFoundError("Knowledge entry not found")
        return row

    def create(
        self,
        organization_id: str,
        *,
        role: str,
        user_id: str,
        payload: KnowledgeEntryCreate,
    ) -> KnowledgeEntry:
        _require_manager(role)
        row = KnowledgeEntry(
            organization_id=organization_id,
            category=payload.category,
            title=payload.title,
            content=payload.content,
            use_in_ai=payload.use_in_ai,
            status=KnowledgeEntryStatus.ACTIVE,
            revision=1,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        self.session.add(row)
        self.session.flush()
        self._record(row, user_id, "Knowledge entry added", "CREATED")
        self.session.commit()
        self.session.refresh(row)
        return row

    def update(
        self,
        organization_id: str,
        entry_id: str,
        *,
        role: str,
        user_id: str,
        payload: KnowledgeEntryUpdate,
    ) -> KnowledgeEntry:
        _require_manager(role)
        row = self.get(organization_id, entry_id)
        if row.revision != payload.expected_revision:
            raise ConflictError(
                "This entry was changed by someone else. Reload it and try again.",
                {"detail": "Knowledge entry revision conflict", "revision": row.revision},
            )
        changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return row
        previous_status = row.status
        for key, value in changes.items():
            setattr(row, key, value)
        row.revision += 1
        row.updated_by_user_id = user_id
        row.updated_at = datetime.now(UTC)
        if row.status != previous_status:
            title = (
                "Knowledge entry archived"
                if row.status == KnowledgeEntryStatus.ARCHIVED
                else "Knowledge entry restored"
            )
        else:
            title = "Knowledge entry updated"
        self.session.flush()
        self._record(row, user_id, title, f"REVISION:{row.revision}")
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete(self, organization_id: str, entry_id: str, *, role: str, user_id: str) -> None:
        _require_manager(role)
        row = self.get(organization_id, entry_id)
        self._record(row, user_id, "Knowledge entry deleted", "DELETED")
        self.session.delete(row)
        self.session.commit()

    def context_for_ai(self, organization_id: str, text: str) -> list[KnowledgeEntry]:
        """Active entries most related to ``text``, within a fixed size budget."""
        candidates = self.session.scalars(
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.organization_id == organization_id,
                KnowledgeEntry.status == KnowledgeEntryStatus.ACTIVE,
                KnowledgeEntry.use_in_ai.is_(True),
            )
            .order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.id)
            .limit(_AI_CANDIDATE_LIMIT)
        ).all()
        query_words = _words(text)
        if not query_words:
            return []
        scored: list[tuple[int, int, KnowledgeEntry]] = []
        for position, entry in enumerate(candidates):
            score = 2 * len(query_words & _words(entry.title)) + len(
                query_words & _words(entry.content)
            )
            if score > 0:
                scored.append((score, -position, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

        chosen: list[KnowledgeEntry] = []
        used = 0
        for _, _, entry in scored:
            size = len(entry.title) + len(entry.content)
            if used + size > AI_CONTEXT_CHAR_BUDGET:
                continue
            chosen.append(entry)
            used += size
            if len(chosen) >= AI_CONTEXT_MAX_ENTRIES:
                break
        return chosen

    def _record(self, row: KnowledgeEntry, user_id: str, title: str, marker: str) -> None:
        ActivityService(self.session).record(
            organization_id=row.organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            actor_user_id=user_id,
            title=title,
            summary=f"{row.title[:120]} ({_CATEGORY_LABELS[KnowledgeCategory(row.category)]})",
            entity_type=ActivityEntityType.KNOWLEDGE_ENTRY,
            entity_id=row.id,
            status=row.status,
            dedupe_key=f"knowledge:{row.id}:{marker}",
        )
