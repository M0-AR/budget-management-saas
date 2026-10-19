import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError, buildQuery, uploadFile } from "../lib/api";
import type { ImportSummary } from "../lib/types";
import { Button, Dialog, Field, useToast } from "./ui";

type Kind = "expense" | "income";

export function ImportCsvDialog({
  kind,
  open,
  onClose,
}: {
  kind: Kind;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);

  const reset = useCallback(() => {
    setFile(null);
    setSkipDuplicates(true);
    setError(null);
    setSummary(null);
    if (fileInput.current) fileInput.current.value = "";
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  const onImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const result = await uploadFile<ImportSummary>(
        `/api/v1/imports/transactions${buildQuery({
          kind,
          skip_duplicates: skipDuplicates ? undefined : "false",
        })}`,
        file,
      );
      setSummary(result);
      const added = result.imported_expenses + result.imported_incomes;
      push({
        tone: added > 0 ? "success" : "info",
        title:
          added > 0
            ? `Imported ${added} ${added === 1 ? "entry" : "entries"}`
            : "Nothing imported",
        description:
          result.failed > 0
            ? `${result.failed} ${result.failed === 1 ? "row" : "rows"} could not be read.`
            : undefined,
      });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    } catch (caught) {
      setError(
        caught instanceof ApiRequestError ? caught.detail : "The import failed — please try again.",
      );
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Import from CSV"
      description="Upload a CSV of transactions — we'll add the rows to this workspace."
      footer={
        summary ? (
          <>
            <Button variant="secondary" onClick={reset}>
              Import another file
            </Button>
            <Button onClick={onClose}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button loading={importing} disabled={!file} onClick={() => void onImport()}>
              Import
            </Button>
          </>
        )
      }
    >
      {summary ? (
        <div className="space-y-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-line bg-surface-2/50 px-4 py-3 sm:grid-cols-4">
            <div>
              <dt className="text-xs text-ink-muted">Expenses added</dt>
              <dd className="tnum text-lg font-semibold">{summary.imported_expenses}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Income added</dt>
              <dd className="tnum text-lg font-semibold">{summary.imported_incomes}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Duplicates skipped</dt>
              <dd className="tnum text-lg font-semibold">{summary.duplicates_skipped}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Rows failed</dt>
              <dd className="tnum text-lg font-semibold">{summary.failed}</dd>
            </div>
          </dl>

          {summary.categories_created > 0 ? (
            <p className="text-sm text-ink-muted">
              {summary.categories_created}{" "}
              {summary.categories_created === 1 ? "new category was" : "new categories were"} created
              for names found in the file.
            </p>
          ) : null}

          {summary.errors.length > 0 ? (
            <div className="rounded-xl border border-danger/30 bg-danger-soft/40 p-3">
              <p className="text-xs font-semibold tracking-wide text-danger uppercase">
                Line-level problems
              </p>
              <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs text-ink-muted">
                {summary.errors.map((rowError) => (
                  <li key={`${rowError.row}-${rowError.message}`}>
                    <span className="tnum font-semibold text-ink">Line {rowError.row}</span> —{" "}
                    {rowError.message}
                  </li>
                ))}
              </ul>
              {summary.failed > summary.errors.length ? (
                <p className="mt-1 text-xs text-ink-muted">
                  …and {summary.failed - summary.errors.length} more.
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          <Field
            label="CSV file"
            hint="Up to 1 MB, max 1000 rows. Required columns: date and amount — optionally note, category and type."
          >
            {(id) => (
              <input
                ref={fileInput}
                id={id}
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setError(null);
                }}
                className="block w-full cursor-pointer rounded-xl border border-line bg-surface-1 text-sm text-ink-muted file:mr-3 file:cursor-pointer file:rounded-l-xl file:border-0 file:border-r file:border-line file:bg-surface-2 file:px-4 file:py-2.5 file:text-sm file:font-medium file:text-ink hover:file:bg-line/60"
              />
            )}
          </Field>

          <p className="text-xs text-ink-muted">
            Dates accept <span className="tnum">YYYY-MM-DD</span> or{" "}
            <span className="tnum">MM/DD/YYYY</span>. Amounts may include $ and commas. A{" "}
            <span className="tnum">type</span> column of <span className="tnum">expense</span> or{" "}
            <span className="tnum">income</span> imports mixed files; otherwise every row is treated
            as {kind === "expense" ? "an expense" : "income"}.
          </p>

          <label className="flex items-start gap-2.5 text-sm">
            <input
              type="checkbox"
              checked={skipDuplicates}
              onChange={(event) => setSkipDuplicates(event.target.checked)}
              className="mt-0.5 size-4 accent-accent"
            />
            <span>
              Skip duplicates
              <span className="block text-xs text-ink-muted">
                Rows matching an existing entry (same date, amount and note) are skipped.
              </span>
            </span>
          </label>

          {error ? (
            <p role="alert" className="text-sm font-medium text-danger">
              {error}
            </p>
          ) : null}
        </div>
      )}
    </Dialog>
  );
}
