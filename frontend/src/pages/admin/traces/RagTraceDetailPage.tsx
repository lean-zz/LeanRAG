import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Copy, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getRagTraceDetail, type EvidenceItem, type RagTraceDetail, type RagTraceNode } from "@/services/ragTraceService";
import { getErrorMessage } from "@/utils/error";
import { formatDateTime, formatDuration, nodeTypeChipClass, statusBadgeVariant, statusLabel } from "@/pages/admin/traces/traceUtils";
import { cn } from "@/lib/utils";

const decodeTraceId = (value?: string): string => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const copyToClipboard = (text: string, label: string) => {
  navigator.clipboard.writeText(text).then(
    () => toast.success(`${label} copied`),
    () => toast.error("Copy failed")
  );
};

function SummaryCard({ detail }: { detail: RagTraceDetail }) {
  const run = detail.run;
  const failedNodes = detail.nodes.filter((node) => String(node.status || "").toLowerCase() === "failed").length;

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm font-medium text-slate-700">{run.traceName || run.question || "RAG trace"}</CardTitle>
          <Badge variant={statusBadgeVariant(run.status)}>{statusLabel(run.status)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 px-4 pb-4 pt-0 text-sm md:grid-cols-4">
        <Metric label="Trace Id" value={run.traceId} mono copy />
        <Metric label="Started" value={formatDateTime(run.startTime ?? undefined)} />
        <Metric label="Latency" value={formatDuration(run.latencyMs ?? run.durationMs ?? undefined)} />
        <Metric label="Failed nodes" value={String(failedNodes)} tone={failedNodes > 0 ? "error" : "success"} />
      </CardContent>
    </Card>
  );
}

function ReliabilityCard({ detail }: { detail: RagTraceDetail }) {
  const run = detail.run;
  const evidence = detail.evidence || [];
  const decision = (detail.decisions || [])[0];
  const guardrailBlocked = run.guardrailSummary?.startsWith("block");

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <ShieldCheck className="h-4 w-4 text-blue-600" />
            Reliability
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{run.variant || "baseline"}</Badge>
            <Badge variant={guardrailBlocked ? "destructive" : "secondary"}>{run.guardrailSummary || "allow:none"}</Badge>
            <Badge variant={decision?.type === "answer" ? "default" : "secondary"}>{decision?.type || "unknown"}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 px-4 pb-4 pt-0">
        <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-4">
          <Metric label="Mode" value={run.mode || "rag"} />
          <Metric label="Evidence" value={String(evidence.length)} />
          <Metric label="Confidence" value={decision?.confidence == null ? "-" : String(decision.confidence)} />
          <Metric label="Reasons" value={(decision?.reasons || []).join(", ") || "-"} />
        </div>
        <EvidenceList evidence={evidence} />
      </CardContent>
    </Card>
  );
}

function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (!evidence.length) {
    return <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">No structured evidence was recorded for this run.</div>;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Evidence chain</p>
      <div className="grid gap-2">
        {evidence.map((item) => (
          <div key={`${item.id}-${item.locator || item.sourceId || ""}`} className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Badge variant="outline">{item.id}</Badge>
              <span className="font-medium text-slate-800">{item.title || item.sourceId || item.kind}</span>
              <span className="text-xs text-slate-500">{item.kind}</span>
              {item.channel && <span className="text-xs text-slate-500">{item.channel}</span>}
              {item.score != null && <span className="text-xs text-slate-500">score {item.score}</span>}
            </div>
            <p className="line-clamp-2 text-slate-600">{item.snippet || item.locator || "-"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function NodesCard({ nodes }: { nodes: RagTraceNode[] }) {
  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium text-slate-700">Trace nodes</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {nodes.length === 0 ? (
          <div className="p-6 text-center text-sm text-slate-500">No trace nodes recorded.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {nodes.map((node) => (
              <div key={node.nodeId} className="grid grid-cols-[minmax(160px,1fr)_120px_110px_1fr] gap-3 px-4 py-3 text-sm">
                <span className="truncate font-medium text-slate-800" title={node.nodeName || node.nodeId}>{node.nodeName || node.nodeId}</span>
                <span className={cn("w-fit rounded px-2 py-0.5 text-xs", nodeTypeChipClass(node.nodeType))}>{node.nodeType || "-"}</span>
                <Badge variant={statusBadgeVariant(node.status)} className="w-fit">{statusLabel(node.status)}</Badge>
                <span className="truncate text-xs text-slate-500">{node.errorMessage || node.extraData || ""}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, mono, copy, tone }: { label: string; value?: string | null; mono?: boolean; copy?: boolean; tone?: "success" | "error" }) {
  const content = value || "-";
  return (
    <div className="min-w-0">
      <p className="text-xs text-slate-500">{label}</p>
      <p
        className={cn(
          "truncate text-sm font-medium text-slate-800",
          mono && "font-mono",
          tone === "success" && "text-emerald-700",
          tone === "error" && "text-red-700",
          copy && "cursor-pointer hover:text-blue-600"
        )}
        title={content}
        onClick={copy ? () => copyToClipboard(content, label) : undefined}
      >
        {content}
        {copy && <Copy className="ml-1 inline h-3 w-3 text-slate-300" />}
      </p>
    </div>
  );
}

export function RagTraceDetailPage() {
  const params = useParams<{ traceId: string }>();
  const traceId = decodeTraceId(params.traceId);
  const requestRef = useRef(0);
  const [detail, setDetail] = useState<RagTraceDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const loadDetail = async () => {
    if (!traceId) return;
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const result = await getRagTraceDetail(traceId);
      if (requestRef.current === requestId) setDetail(result);
    } catch (error) {
      if (requestRef.current !== requestId) return;
      toast.error(getErrorMessage(error, "Failed to load trace detail"));
      setDetail(null);
    } finally {
      if (requestRef.current === requestId) setLoading(false);
    }
  };

  useEffect(() => {
    requestRef.current += 1;
    setDetail(null);
    if (traceId) void loadDetail();
  }, [traceId]);

  const title = useMemo(() => detail?.run.traceName || detail?.run.question || "Trace detail", [detail]);

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading trace detail...
      </div>
    );
  }

  if (!traceId || !detail) {
    return (
      <div className="space-y-6">
        <Header title="Trace detail" onRefresh={loadDetail} loading={loading} />
        <div className="flex min-h-[300px] flex-col items-center justify-center text-slate-500">
          <AlertTriangle className="mb-3 h-10 w-10 text-slate-300" />
          <p>{traceId ? "No trace data found." : "Missing Trace Id."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-8">
      <Header title={title} onRefresh={loadDetail} loading={loading} />
      <SummaryCard detail={detail} />
      <ReliabilityCard detail={detail} />
      <NodesCard nodes={detail.nodes || []} />
    </div>
  );
}

function Header({ title, onRefresh, loading }: { title: string; onRefresh: () => void; loading: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="mb-1 flex items-center gap-1.5 text-sm text-slate-500">
          <Link to="/admin/traces" className="hover:text-slate-700">Trace list</Link>
          <span>/</span>
          <span>Detail</span>
        </div>
        <h1 className="truncate text-lg font-semibold text-slate-900">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <Button asChild variant="outline" size="sm">
          <Link to="/admin/traces">
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            Back
          </Link>
        </Button>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={cn("mr-1.5 h-4 w-4", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>
    </div>
  );
}
