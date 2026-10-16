"use client";

import {
  AlertCircle,
  Check,
  FileSpreadsheet,
  LoaderCircle,
  RotateCcw,
  Upload,
  UserPlus,
} from "lucide-react";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { importProspectCsv, previewProspectCsv } from "@/lib/api/prospect-discovery";
import type {
  ProspectImportResponse,
  ProspectPreviewIssue,
  ProspectPreviewResponse,
  ProspectPreviewRow,
} from "@/types/api";

const MAX_FILE_SIZE = 2 * 1024 * 1024;
const ACCEPTED_TYPES = new Set([
  "text/csv",
  "application/csv",
  "application/vnd.ms-excel",
]);

function formatFileSize(size: number) {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function errorMessage(error: unknown, action: "preview" | "import" = "preview") {
  if (error instanceof ApiError && typeof error.body === "object" && error.body) {
    const detail = (error.body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return action === "import"
    ? "The import could not be completed. Check your connection and try again."
    : "The file could not be previewed. Check your connection and try again.";
}

function duplicateLabel(row: ProspectPreviewRow) {
  return row.duplicate_reasons
    .map((reason) => {
      if (reason === "EXISTING_EMAIL") {
        return "Email matches a lead in this organization";
      }
      if (reason === "IN_FILE_EMAIL") {
        return `Email duplicates row ${row.duplicate_of_row ?? "in this file"}`;
      }
      if (reason === "IN_FILE_NAME_COMPANY") {
        return "Name and company match another row in this file";
      }
      return "Possible duplicate";
    })
    .join("; ");
}

function IssueList({ issues }: { issues: ProspectPreviewIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <ul className="grid gap-1 text-sm" aria-label="File validation messages">
      {issues.map((issue, index) => (
        <li
          key={`${issue.code}-${issue.row_number ?? "file"}-${index}`}
          className={
            issue.severity === "warning"
              ? "text-warning-text"
              : "text-danger-text"
          }
        >
          {issue.row_number ? `Row ${issue.row_number}: ` : "File: "}
          {issue.message}
        </li>
      ))}
    </ul>
  );
}

function PreviewTable({ preview }: { preview: ProspectPreviewResponse }) {
  if (preview.rows.length === 0) {
    return (
      <p className="text-muted-foreground border-border border-t py-5 text-sm">
        No data rows found in this file.
      </p>
    );
  }

  return (
    <div className="border-border overflow-x-auto border-y">
      <table className="w-full min-w-176 border-collapse text-left text-sm">
        <thead className="bg-muted/60 text-muted-foreground sticky top-0 text-xs">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Row</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
            {preview.columns.map((column) => (
              <th scope="col" key={column.index} className="px-3 py-2 font-medium">
                <span>{column.label || `Column ${column.index + 1}`}</span>
                {column.field ? (
                  <span className="text-muted-foreground/70 ml-1 font-normal">
                    {column.field}
                  </span>
                ) : null}
              </th>
            ))}
            <th scope="col" className="px-3 py-2 font-medium">Validation</th>
            <th scope="col" className="px-3 py-2 font-medium">Duplicate check</th>
          </tr>
        </thead>
        <tbody className="divide-border divide-y">
          {preview.rows.map((row) => (
            <tr key={row.row_number} className="align-top">
              <th scope="row" className="text-muted-foreground px-3 py-3 font-mono text-xs">
                {row.row_number}
              </th>
              <td className="px-3 py-3">
                <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                  {row.valid ? (
                    <Check className="text-success-text size-4" aria-hidden="true" />
                  ) : (
                    <AlertCircle className="text-danger-text size-4" aria-hidden="true" />
                  )}
                  {row.valid ? "Valid" : "Invalid"}
                </span>
              </td>
              {preview.columns.map((column) => (
                <td
                  key={column.index}
                  className="text-foreground max-w-64 px-3 py-3 wrap-break-word"
                >
                  {row.cells[column.index] ?? (
                    <span className="text-muted-foreground italic">Missing</span>
                  )}
                </td>
              ))}
              <td className="text-danger-text max-w-64 px-3 py-3">
                {row.errors.length ? (
                  <ul className="grid gap-1">
                    {row.errors.map((issue, index) => (
                      <li key={`${issue.code}-${index}`}>{issue.message}</li>
                    ))}
                  </ul>
                ) : <span className="text-muted-foreground">None</span>}
              </td>
              <td className="max-w-64 px-3 py-3">
                {row.duplicate_reasons.length ? (
                  <span className="text-warning-text">{duplicateLabel(row)}</span>
                ) : <span className="text-muted-foreground">No match found</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ImportResults({ result }: { result: ProspectImportResponse }) {
  const completeFailure =
    result.imported_count === 0 && result.failed_count > 0;
  const partialSuccess =
    result.imported_count > 0 &&
    (result.skipped_count > 0 || result.failed_count > 0);
  const title = completeFailure
    ? "Import failed"
    : partialSuccess
      ? "Partial import complete"
      : result.imported_count > 0
        ? "Import complete"
        : "No prospects imported";

  return (
    <section
      aria-labelledby="import-result-title"
      role={completeFailure ? "alert" : "status"}
      className="border-border grid gap-3 border-y py-4"
    >
      <div>
        <h3 id="import-result-title" className="text-sm font-semibold">
          {title}
        </h3>
        <p className="text-muted-foreground mt-1 text-sm">
          {result.imported_count} imported, {result.skipped_count} skipped,{" "}
          {result.failed_count} failed.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-96 border-collapse text-left text-sm">
          <thead className="text-muted-foreground border-border border-b text-xs">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">
                Row
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                Result
              </th>
              <th scope="col" className="py-2 font-medium">
                Reason
              </th>
            </tr>
          </thead>
          <tbody className="divide-border divide-y">
            {result.rows.map((row) => (
              <tr key={row.row_number}>
                <th
                  scope="row"
                  className="text-muted-foreground py-2 pr-4 font-mono text-xs"
                >
                  {row.row_number}
                </th>
                <td className="py-2 pr-4">{row.status.toLowerCase()}</td>
                <td className="text-muted-foreground py-2">
                  {row.message ?? "Lead created."}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ProspectDiscoveryPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const importInFlightRef = useRef(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ProspectPreviewResponse | null>(null);
  const [importResult, setImportResult] =
    useState<ProspectImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  function selectFile(candidate?: File) {
    if (!candidate) return;
    setPreview(null);
    setImportResult(null);
    setImportError(null);
    setConfirmed(false);
    setUploadError(null);
    setFileError(null);
    if (!candidate.name.toLocaleLowerCase().endsWith(".csv")) {
      setFile(null);
      setFileError("Choose a file with the .csv extension.");
      return;
    }
    if (candidate.type && !ACCEPTED_TYPES.has(candidate.type.toLowerCase())) {
      setFile(null);
      setFileError("This file type is not supported. Choose a CSV file.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null);
      setFileError("CSV files must be 2 MiB or smaller.");
      return;
    }
    setFile(candidate);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.currentTarget.files?.[0]);
    event.currentTarget.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    selectFile(event.dataTransfer.files[0]);
  }

  async function runPreview() {
    if (!file || isLoading || isImporting) return;
    setIsLoading(true);
    setUploadError(null);
    setPreview(null);
    setImportResult(null);
    setImportError(null);
    setConfirmed(false);
    try {
      setPreview(await previewProspectCsv(file));
    } catch (error) {
      setUploadError(errorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }

  async function runImport() {
    if (
      !file ||
      !preview ||
      !confirmed ||
      importInFlightRef.current ||
      importResult
    )
      return;
    importInFlightRef.current = true;
    setIsImporting(true);
    setImportError(null);
    try {
      setImportResult(await importProspectCsv(file));
    } catch (error) {
      setImportError(errorMessage(error, "import"));
    } finally {
      importInFlightRef.current = false;
      setIsImporting(false);
    }
  }

  const eligibleCount = preview
    ? preview.rows.filter(
        (row) => row.valid && row.duplicate_reasons.length === 0,
      ).length
    : 0;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Prospect Discovery"
        description="Review and validate business prospects from a CSV before any CRM action."
      />

      <section aria-labelledby="csv-upload-title" className="grid gap-4">
        <div>
          <h2 id="csv-upload-title" className="text-sm font-semibold">CSV file</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            UTF-8 CSV, up to 2 MiB and 500 data rows.
          </p>
        </div>
        <label
          htmlFor="prospect-csv-file"
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`border-border bg-muted/30 hover:bg-muted/50 focus-within:ring-ring grid min-h-36 cursor-pointer place-items-center border border-dashed px-5 py-6 text-center transition-colors focus-within:ring-2 ${isDragging ? "border-primary bg-primary/5" : ""}`}
        >
          <input
            ref={inputRef}
            id="prospect-csv-file"
            type="file"
            accept=".csv,text/csv,application/csv"
            aria-label="Choose CSV file"
            className="sr-only"
            disabled={isLoading || isImporting}
            onChange={handleFileChange}
          />
          <span className="grid justify-items-center gap-2">
            <FileSpreadsheet className="text-primary size-6" aria-hidden="true" />
            <span className="text-sm font-medium">
              {file ? file.name : "Choose a CSV or drop it here"}
            </span>
            <span className="text-muted-foreground text-xs">
              {file ? formatFileSize(file.size) : "CSV files only · 2 MiB maximum"}
            </span>
          </span>
        </label>
        {fileError ? <p role="alert" className="text-danger-text text-sm">{fileError}</p> : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            onClick={() => void runPreview()}
            disabled={!file || isLoading || isImporting}
          >
            {isLoading ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : preview ? (
              <RotateCcw aria-hidden="true" />
            ) : (
              <Upload aria-hidden="true" />
            )}
            {isLoading ? "Validating CSV" : preview ? "Preview again" : "Preview CSV"}
          </Button>
          <p className="text-muted-foreground text-xs" aria-live="polite">
            Review every row before confirming an import.
          </p>
        </div>
      </section>

      {uploadError ? (
        <div role="alert" className="border-destructive/40 bg-destructive/5 flex flex-wrap items-center justify-between gap-3 border px-4 py-3">
          <p className="text-danger-text flex items-center gap-2 text-sm">
            <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
            {uploadError}
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => void runPreview()} disabled={isLoading || !file}>
            Retry preview
          </Button>
        </div>
      ) : null}

      {isLoading || isImporting ? (
        <p role="status" className="text-muted-foreground flex items-center gap-2 py-3 text-sm">
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          {isImporting ? "Importing confirmed prospects…" : "Reading and validating CSV rows…"}
        </p>
      ) : null}

      {preview ? (
        <section aria-labelledby="preview-title" className="grid gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="preview-title" className="text-sm font-semibold">Preview results</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Detected columns are shown using their original header labels.
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-5 gap-y-2 sm:grid-cols-4">
              {[
                ["Rows", preview.summary.total_rows],
                ["Valid", preview.summary.valid_rows],
                ["Invalid", preview.summary.invalid_rows],
                ["Duplicates", preview.summary.duplicate_rows],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-muted-foreground text-xs">{label}</dt>
                  <dd className="text-foreground mt-0.5 text-sm font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <IssueList issues={preview.issues} />
          <PreviewTable preview={preview} />
          <section
            aria-labelledby="import-review-title"
            className="border-border grid gap-3 border-t pt-4"
          >
            <div>
              <h2 id="import-review-title" className="text-sm font-semibold">
                Review and import
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                {eligibleCount} valid, non-duplicate{" "}
                {eligibleCount === 1 ? "prospect is" : "prospects are"}{" "}
                eligible. {preview.summary.total_rows - eligibleCount} invalid
                or duplicate{" "}
                {preview.summary.total_rows - eligibleCount === 1
                  ? "row will be"
                  : "rows will be"}{" "}
                skipped. Existing leads will never be overwritten. Imported
                records are created as new CRM leads.
              </p>
            </div>
            <label className="flex max-w-2xl items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={
                  !eligibleCount || isImporting || importResult !== null
                }
                onChange={(event) => setConfirmed(event.currentTarget.checked)}
                className="border-input accent-primary mt-0.5 size-4 shrink-0"
              />
              <span>
                I confirm that eligible prospects should be added to this
                organization&apos;s CRM.
              </span>
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                onClick={() => void runImport()}
                disabled={
                  !eligibleCount ||
                  !confirmed ||
                  isImporting ||
                  isLoading ||
                  importResult !== null
                }
              >
                {isImporting ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : (
                  <UserPlus aria-hidden="true" />
                )}
                {isImporting
                  ? "Importing prospects"
                  : `Import ${eligibleCount} eligible leads`}
              </Button>
              {importResult ? (
                <span className="text-muted-foreground text-sm">
                  {importResult.failed_count > 0
                    ? "Preview this file again before retrying failed rows; email duplicates will be skipped."
                    : "This file has already been submitted."}
                </span>
              ) : null}
            </div>
            {importError ? (
              <div
                role="alert"
                className="border-destructive/40 bg-destructive/5 flex items-center gap-2 border px-4 py-3 text-sm"
              >
                <AlertCircle
                  className="text-danger-text size-4 shrink-0"
                  aria-hidden="true"
                />
                <span className="text-danger-text">{importError}</span>
              </div>
            ) : null}
            {importResult ? <ImportResults result={importResult} /> : null}
          </section>
        </section>
      ) : !isLoading && !uploadError ? (
        <section aria-labelledby="empty-preview-title" className="border-border border-t py-6">
          <h2 id="empty-preview-title" className="text-sm font-medium">No preview yet</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Choose a CSV file to see its columns, validation results, and duplicate checks.
          </p>
        </section>
      ) : null}
    </div>
  );
}
