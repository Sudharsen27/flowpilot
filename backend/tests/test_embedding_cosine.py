from app.ai.embedding_provider import cosine_similarity, dump_embedding, load_embedding


def test_cosine_similarity_and_round_trip() -> None:
    left = [1.0, 0.0, 0.0]
    right = [1.0, 0.0, 0.0]
    assert cosine_similarity(left, right) == 1.0
    assert cosine_similarity(left, [0.0, 1.0, 0.0]) == 0.0
    assert load_embedding(dump_embedding(left)) == left
