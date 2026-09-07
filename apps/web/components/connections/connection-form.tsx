"use client"

import * as React from "react"
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, XCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input, Select, Textarea } from "@/components/ui/input"
import {
  type Connector,
  type ConnectionTestResult,
  testConnection,
} from "@/lib/api"
import { cn } from "@/lib/utils"

/**
 * Renders a platform's configuration form from its declared field spec.
 *
 * Nothing here is per-platform: the form is generated from the connector's
 * fields, so adding a platform on the server adds it here with no UI change.
 */
export function ConnectionForm({ connector }: { connector: Connector }) {
  const initial = React.useMemo(
    () =>
      Object.fromEntries(
        connector.fields.map((f) => [f.name, f.default ?? ""])
      ) as Record<string, string>,
    [connector]
  )

  const [values, setValues] = React.useState<Record<string, string>>(initial)
  const [result, setResult] = React.useState<ConnectionTestResult | null>(null)
  const [testing, setTesting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Switching platform must clear both the values and any previous result, or a
  // stale green tick reads as if the new platform is already connected.
  React.useEffect(() => {
    setValues(initial)
    setResult(null)
    setError(null)
  }, [initial])

  const missing = connector.fields
    .filter((f) => f.required && !values[f.name]?.trim())
    .map((f) => f.label)

  async function handleTest() {
    setTesting(true)
    setResult(null)
    setError(null)
    try {
      setResult(await testConnection(connector.id, values))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong")
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-h1">{connector.name}</h2>
          {connector.verified ? (
            <Badge tone="success">Verified</Badge>
          ) : (
            <Badge tone="warning">Not yet verified</Badge>
          )}
        </div>
        <p className="mt-1 text-muted-foreground">{connector.description}</p>
        {connector.docs_url ? (
          <a
            href={connector.docs_url}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-1.5 inline-flex items-center gap-1 text-caption text-primary hover:underline"
          >
            Where to find these values <ExternalLink className="size-3" />
          </a>
        ) : null}
      </div>

      {!connector.verified ? (
        <div className="flex items-start gap-2 rounded-md border border-border bg-warning-soft/40 p-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
          <p className="text-caption text-muted-foreground">
            This connector has not yet been run against a real {connector.name}{" "}
            account. It is built to the documented API, but you will be the first
            to exercise it — please report anything that misbehaves.
          </p>
        </div>
      ) : null}

      {!connector.driver_available ? (
        <div className="flex items-start gap-2 rounded-md border border-border bg-danger-soft/40 p-2.5">
          <XCircle className="mt-0.5 size-4 shrink-0 text-danger" />
          <p className="text-caption text-muted-foreground">
            The driver for {connector.name} is not installed on the server. Install{" "}
            <span className="font-mono">{connector.driver_package}</span> and restart
            the API.
          </p>
        </div>
      ) : null}

      <div className="flex flex-col gap-3">
        {connector.fields.map((field) => (
          <label key={field.name} className="flex flex-col gap-1">
            <span className="text-caption font-medium">
              {field.label}
              {!field.required ? (
                <span className="ml-1 font-normal text-muted-foreground">optional</span>
              ) : null}
            </span>

            {field.type === "textarea" ? (
              <Textarea
                value={values[field.name] ?? ""}
                placeholder={field.placeholder ?? undefined}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [field.name]: e.target.value }))
                }
              />
            ) : field.type === "select" ? (
              <Select
                value={values[field.name] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [field.name]: e.target.value }))
                }
              >
                {field.options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                // Secrets use a password input so they are not shoulder-readable
                // and are excluded from browser autofill heuristics.
                type={
                  field.type === "secret"
                    ? "password"
                    : field.type === "number"
                      ? "number"
                      : "text"
                }
                value={values[field.name] ?? ""}
                placeholder={field.placeholder ?? undefined}
                autoComplete={field.type === "secret" ? "new-password" : "off"}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [field.name]: e.target.value }))
                }
              />
            )}

            {field.help ? (
              <span className="text-caption text-muted-foreground">{field.help}</span>
            ) : null}
          </label>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          onClick={handleTest}
          disabled={testing || missing.length > 0}
          title={missing.length ? `Still needed: ${missing.join(", ")}` : undefined}
        >
          {testing ? <Loader2 className="size-4 animate-spin" /> : null}
          {testing ? "Testing…" : "Test connection"}
        </Button>
        {missing.length > 0 ? (
          <span className="text-caption text-muted-foreground">
            Still needed: {missing.join(", ")}
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-danger/40 bg-danger-soft/40 p-2.5">
          <XCircle className="mt-0.5 size-4 shrink-0 text-danger" />
          <p className="text-caption">{error}</p>
        </div>
      ) : null}

      {result ? (
        <div
          className={cn(
            "flex flex-col gap-2 rounded-md border p-3",
            result.ok
              ? "border-success/40 bg-success-soft/40"
              : "border-danger/40 bg-danger-soft/40"
          )}
        >
          <div className="flex items-start gap-2">
            {result.ok ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
            ) : (
              <XCircle className="mt-0.5 size-4 shrink-0 text-danger" />
            )}
            <p className="min-w-0 break-words">{result.message}</p>
          </div>
          {Object.keys(result.details).length > 0 ? (
            // Evidence that something was genuinely read, so a green tick means
            // more than "a socket opened".
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 pl-6 text-caption">
              {Object.entries(result.details).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
                  <dd className="font-mono break-all">{v}</dd>
                </React.Fragment>
              ))}
            </dl>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
