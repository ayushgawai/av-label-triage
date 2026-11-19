import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Box = number[];
type Frame = {
  id: string;
  path: string;
  width: number;
  height: number;
  sha256: string;
  metadata: Record<string, any>;
};
type Proposal = {
  id: string;
  image_id: string;
  bbox: Box;
  score: number;
  confidence_rank: number;
  similarity_rank: number | null;
  match_status: string;
};
type Bundle = {
  incident: { id: string; image_id: string; bbox: Box };
  release: { id: string; dataset_revision: string };
  images: Frame[];
  annotations: { id: string; image_id: string; bbox: Box; category: string }[];
  queue: Proposal[];
  review_events: unknown[];
  audit: null | any;
};
type Decision = {
  incident: string;
  proposal: string;
  decision: string;
  id: string;
  supersedes: string | null;
};
const liveIncident = new URLSearchParams(location.search).get("incident");
const labels: Record<string, string> = {
  omission: "Missed pedestrian",
  already_labeled: "Already labeled",
  localization_error: "Box needs adjustment",
  out_of_scope: "Out of scope",
  unresolved: "Needs another look",
};
function LiveAudit({
  incident,
  initialDesign = "",
}: {
  incident: string;
  initialDesign?: string;
}) {
  const [budget, setBudget] = useState("3"),
    [design, setDesign] = useState(initialDesign),
    [blind, setBlind] = useState<any>(null),
    [report, setReport] = useState<any>(null),
    [selected, setSelected] = useState(0),
    [message, setMessage] = useState("");
  useEffect(() => {
    if (!initialDesign) return;
    fetch(`/api/audits/${initialDesign}/blind`)
      .then((r) => {
        if (!r.ok) throw Error("Audit not found");
        return r.json();
      })
      .then(setBlind)
      .catch((e) => setMessage(String(e)));
    fetch(`/api/audits/${initialDesign}/result`)
      .then((r) => r.json())
      .then(setReport);
  }, [initialDesign]);
  async function create() {
    const r = await fetch("/api/audits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        incident_id: incident,
        budget: Number(budget),
        seed: 20261119,
      }),
    });
    if (!r.ok) {
      setMessage(await r.text());
      return;
    }
    const d = await r.json();
    setDesign(d.design_id);
    setBlind(
      await fetch(`/api/audits/${d.design_id}/blind`).then((x) => x.json()),
    );
    setReport(
      await fetch(`/api/audits/${d.design_id}/result`).then((x) => x.json()),
    );
  }
  async function decide(value: string) {
    const actor = prompt("Independent auditor name");
    if (!actor) return;
    const r = await fetch(`/api/audits/${design}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_id: blind.images[selected].id,
        decision: value,
        actor_type: "human",
        actor_id: actor,
      }),
    });
    if (!r.ok) {
      setMessage(await r.text());
      return;
    }
    setReport(
      await fetch(`/api/audits/${design}/result`).then((x) => x.json()),
    );
    setMessage("Decision recorded independently.");
  }
  const frame = blind?.images[selected];
  return (
    <section className="panel">
      <span className="overline">Independent audit</span>
      <h2>Blind full-frame inspection</h2>
      <p>
        Freeze the image sample before reviewing. The inspector sees original
        labels and policy, without queue ranks or model suggestions.
      </p>
      {!design ? (
        <>
          <label>
            Fixed image budget{" "}
            <input
              type="number"
              min="1"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </label>{" "}
          <button onClick={create}>Freeze sample</button>
        </>
      ) : !blind ? (
        <p>Loading frozen sample…</p>
      ) : (
        <>
          <p>
            Design {design.slice(0, 12)} · {report?.completed} of{" "}
            {report?.sampled} resolved · {report?.status}
          </p>
          <p>
            <a href={`/viewer/?audit=${design}`}>Open dedicated blind audit</a>
          </p>
          <details>
            <summary>Label policy</summary>
            <pre>{JSON.stringify(blind.policy, null, 2)}</pre>
          </details>
          <div className="filmstrip">
            {blind.images.map((i: any, n: number) => (
              <button key={i.id} onClick={() => setSelected(n)}>
                Image {i.id}
              </button>
            ))}
          </div>
          {frame && (
            <>
              <div
                className="canvas auditcanvas"
                style={{ aspectRatio: `${frame.width}/${frame.height}` }}
              >
                <img
                  src={`/api/images/${blind.release_id}/${encodeURIComponent(frame.id)}`}
                  alt={"Audit full frame " + frame.id}
                />
                {frame.annotations.map((a: any) => {
                  const b = JSON.parse(a.bbox_json);
                  return (
                    <div
                      key={a.id}
                      className="box original"
                      style={{
                        left: `${(100 * b[0]) / frame.width}%`,
                        top: `${(100 * b[1]) / frame.height}%`,
                        width: `${(100 * (b[2] - b[0])) / frame.width}%`,
                        height: `${(100 * (b[3] - b[1])) / frame.height}%`,
                      }}
                    >
                      <span>{a.category}</span>
                    </div>
                  );
                })}
              </div>
              <p>
                Image {frame.id} · inspect the entire frame under policy{" "}
                {blind.policy_id.slice(0, 12)}.
              </p>
              <div className="actions">
                <button onClick={() => decide("omission")}>
                  Omitted pedestrian present
                </button>
                <button onClick={() => decide("no_omission")}>
                  No omission found
                </button>
                <button onClick={() => decide("unresolved")}>Unresolved</button>
              </div>
            </>
          )}
          {report?.status === "complete" && (
            <p>
              Estimate {(report.estimate * 100).toFixed(1)}%, 95% interval{" "}
              {(report.lower * 100).toFixed(1)}–
              {(report.upper * 100).toFixed(1)}%.
            </p>
          )}
        </>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
function App() {
  const [flashEnabled, setFlashEnabled] = useState(false),
    [flashStatus, setFlashStatus] = useState("");
  useEffect(() => {
    if (liveIncident)
      fetch("/api/flash/status")
        .then((r) => r.json())
        .then((x) => setFlashEnabled(x.enabled))
        .catch(() => {});
  }, []);
  const [auditImage, setAuditImage] = useState("");
  const [region, setRegion] = useState(""),
    [seedImage, setSeedImage] = useState(""),
    [seedBox, setSeedBox] = useState("");
  const [caseNo, setCaseNo] = useState(3),
    [bundle, setBundle] = useState<Bundle | null>(null),
    [selected, setSelected] = useState(-1),
    [view, setView] = useState("Investigation"),
    [showOriginal, setShowOriginal] = useState(true),
    [showOther, setShowOther] = useState(false),
    [error, setError] = useState("");
  const [decisions, setDecisions] = useState<Decision[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("avtriage-decisions") || "[]");
    } catch {
      return [];
    }
  });
  useEffect(() => {
    fetch(
      liveIncident
        ? `/api/incidents/${liveIncident}/replay`
        : `./data/${caseNo === 5 ? "case-0" : `photo-${caseNo}`}.json`,
    )
      .then((r) => {
        if (!r.ok) throw Error("Replay unavailable");
        return r.json();
      })
      .then((b) => {
        setBundle(b);
        setAuditImage(b.audit?.blind.images[0]?.id || "");
        setSelected(-1);
      })
      .catch((e) => setError(String(e)));
  }, [caseNo]);
  useEffect(() => {
    localStorage.setItem("avtriage-decisions", JSON.stringify(decisions));
  }, [decisions]);
  const queue = bundle?.queue || [],
    proposal = selected >= 0 ? queue[selected] : null,
    frame = bundle?.images.find(
      (i) => i.id === (proposal?.image_id || bundle.incident.image_id),
    );
  const liveEvents = proposal
    ? ((bundle?.review_events || []).filter(
        (e: any) => e.proposal_id === proposal.id,
      ) as any[])
    : [];
  useEffect(() => {
    setRegion(proposal ? proposal.bbox.join(", ") : "");
  }, [proposal?.id]);
  const current = proposal
    ? liveIncident
      ? liveEvents.length
        ? { decision: liveEvents.at(-1).decision, id: liveEvents.at(-1).id }
        : undefined
      : decisions
          .filter(
            (d) =>
              d.incident === bundle?.incident.id && d.proposal === proposal.id,
          )
          .at(-1)
    : undefined;
  async function decide(decision: string) {
    if (!proposal) return;
    if (liveIncident) {
      const actor = prompt("Reviewer name");
      if (!actor) return;
      const events = (bundle?.review_events || []).filter(
        (e: any) => e.proposal_id === proposal.id,
      ) as any[];
      const r = await fetch(`/api/incidents/${liveIncident}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proposal_id: proposal.id,
          decision,
          actor_type: "human",
          actor_id: actor,
          idempotency_key: crypto.randomUUID(),
          expected_revision: events.length,
          supersedes_id: events.at(-1)?.id || null,
          region: region.split(",").map(Number),
        }),
      });
      if (!r.ok) {
        alert(await r.text());
        return;
      }
      const data = await fetch(`/api/incidents/${liveIncident}/replay`).then(
        (x) => x.json(),
      );
      setBundle(data);
      return;
    }
    setDecisions((x) => [
      ...x,
      {
        incident: bundle!.incident.id,
        proposal: proposal.id,
        decision,
        id: crypto.randomUUID(),
        supersedes: current?.id || null,
      },
    ]);
  }
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement
      )
        return;
      if (e.key === "ArrowRight") {
        setSelected((x) => Math.min(queue.length - 1, x + 1));
        e.preventDefault();
      }
      if (e.key === "ArrowLeft") {
        setSelected((x) => Math.max(-1, x - 1));
        e.preventDefault();
      }
      if (e.key === "1") decide("omission");
      if (e.key === "2") decide("out_of_scope");
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [queue.length, proposal, current]);
  const imagePath = (im: Frame | undefined) =>
    liveIncident && im
      ? `/api/images/${bundle?.release.id}/${encodeURIComponent(im.id)}`
      : "./data/" + im?.path;
  const anns =
    bundle?.annotations.filter(
      (a) =>
        a.image_id === frame?.id && (a.category === "pedestrian" || showOther),
    ) || [];
  const box = (b: Box, kind: string, text: string) =>
    frame && (
      <div
        className={"box " + kind}
        style={{
          left: `${(100 * b[0]) / frame.width}%`,
          top: `${(100 * b[1]) / frame.height}%`,
          width: `${(100 * (b[2] - b[0])) / frame.width}%`,
          height: `${(100 * (b[3] - b[1])) / frame.height}%`,
        }}
      >
        <span>{text}</span>
      </div>
    );
  return (
    <>
      <header>
        <div className="brand">
          <b>AV</b>
          <span>
            Label Triage<small>Perception quality workbench</small>
          </span>
        </div>
        <nav>
          {["Investigation", "Audit", "Report"].map((v) => (
            <button
              key={v}
              className={v === view ? "active" : ""}
              onClick={() => setView(v)}
            >
              {v}
            </button>
          ))}
        </nav>
        <div className="mode">
          <i /> {liveIncident ? "Local workspace" : "Recorded inference"}
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
      {!bundle || !frame ? (
        <p className="loading">Loading recorded evidence…</p>
      ) : (
        <main>
          <div className="context">
            <div>
              <span className="crumb">
                Investigations / pedestrian omissions
              </span>
              <h1>How many more should we reopen?</h1>
              <p>
                {liveIncident
                  ? "Review each full frame before deciding."
                  : "A deliberately removed COCO annotation is the seed. Review each full frame before deciding."}
              </p>
            </div>
            <div className="release">
              <span>Release</span>
              <strong>{bundle.release.dataset_revision}</strong>
              <small title={bundle.release.id}>
                {bundle.release.id.slice(0, 12)}
              </small>
            </div>
          </div>
          {liveIncident && (
            <details className="newseed">
              <summary>Create another seed by coordinates</summary>
              <label>
                Image ID{" "}
                <input
                  value={seedImage}
                  onChange={(e) => setSeedImage(e.target.value)}
                />
              </label>{" "}
              <label>
                Region x1, y1, x2, y2{" "}
                <input
                  value={seedBox}
                  onChange={(e) => setSeedBox(e.target.value)}
                />
              </label>{" "}
              <button
                onClick={async () => {
                  const r = await fetch("/api/seeds", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      release_id: bundle.release.id,
                      image_id: seedImage,
                      bbox: seedBox.split(",").map(Number),
                      index_fingerprint: (bundle.incident as any)
                        .index_fingerprint,
                    }),
                  });
                  if (!r.ok) {
                    alert(await r.text());
                    return;
                  }
                  const d = await r.json();
                  location.href = "/viewer/?incident=" + d.incident_id;
                }}
              >
                Create seed
              </button>
            </details>
          )}
          {view === "Investigation" ? (
            <div className="workspace">
              <section className="stage">
                <div className="sectionbar">
                  <div>
                    <span className="overline">
                      {selected < 0
                        ? "Incident seed"
                        : `Queue item ${selected + 1} of ${queue.length}`}
                    </span>
                    <h2>Image {frame.id}</h2>
                  </div>
                  <label>
                    <input
                      type="checkbox"
                      checked={showOriginal}
                      onChange={(e) => setShowOriginal(e.target.checked)}
                    />{" "}
                    Original labels
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={showOther}
                      onChange={(e) => setShowOther(e.target.checked)}
                    />{" "}
                    Other classes
                  </label>
                </div>
                <div className="imagewrap">
                  <div
                    key={frame.id}
                    className="canvas"
                    style={{ aspectRatio: `${frame.width}/${frame.height}` }}
                  >
                    <img
                      src={imagePath(frame)}
                      alt={`Full frame ${frame.id}`}
                    />
                    {showOriginal &&
                      anns.map((a) => (
                        <React.Fragment key={a.id}>
                          {box(a.bbox, "original", a.category)}
                        </React.Fragment>
                      ))}
                    {box(
                      proposal?.bbox || bundle.incident.bbox,
                      selected < 0 ? "seed" : "candidate",
                      selected < 0 ? "Seeded omission" : "Proposal",
                    )}
                  </div>
                </div>
                {frame.metadata.attribution && (
                  <p className="credit">
                    Photo:{" "}
                    <a href={frame.metadata.attribution.source}>
                      {frame.metadata.attribution.creator}
                    </a>
                    , <a href={frame.metadata.attribution.license}>CC BY 2.0</a>
                    ; resized COCO derivative. COCO annotations:{" "}
                    <a href="https://creativecommons.org/licenses/by/4.0/">
                      CC BY 4.0
                    </a>
                    .
                  </p>
                )}
                <div className="filmstrip" aria-label="Evidence frames">
                  <button onClick={() => setSelected(-1)}>
                    <img
                      src={imagePath(
                        bundle.images.find(
                          (i) => i.id === bundle.incident.image_id,
                        ),
                      )}
                      alt="Seed frame"
                    />
                    <span>Seed</span>
                  </button>
                  {queue.slice(0, 6).map((p, i) => {
                    const im = bundle.images.find((x) => x.id === p.image_id);
                    return (
                      <button key={p.id} onClick={() => setSelected(i)}>
                        <img
                          src={imagePath(im)}
                          alt={`Open image ${p.image_id}`}
                        />
                        <span>{p.image_id}</span>
                      </button>
                    );
                  })}
                </div>
                <div className="legend">
                  <span>
                    <i className="teal" /> Original label
                  </span>
                  <span>
                    <i className="amber" />{" "}
                    {selected < 0 ? "Seed region" : "Suggested region"}
                  </span>
                  <span>
                    Full frame · {frame.width} × {frame.height}
                  </span>
                </div>
                <div className="explain">
                  <strong>
                    {selected < 0
                      ? liveIncident
                        ? "Incident seed"
                        : "A deliberately omitted pedestrian"
                      : "Review this suggestion"}
                  </strong>
                  <p>
                    {selected < 0
                      ? liveIncident
                        ? "This is the selected incident region."
                        : "This original COCO person annotation was deliberately removed to create the seed."
                      : "Inspect this suggestion in the full frame before making a decision."}
                  </p>
                </div>
              </section>
              <aside>
                <div className="queuehead">
                  <div>
                    <span className="overline">Review queue</span>
                    <h2>{queue.length} suggestions</h2>
                  </div>
                  <button
                    className="textbutton"
                    onClick={() => setSelected(-1)}
                  >
                    Seed
                  </button>
                </div>
                <p className="muted">
                  One suggestion per image. Seed and known duplicate excluded.
                </p>
                <div className="queue">
                  {queue.map((p, i) => (
                    <button
                      key={p.id}
                      className={
                        "queueitem " + (i === selected ? "chosen" : "")
                      }
                      onClick={() => setSelected(i)}
                    >
                      <span className="rank">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>Image {p.image_id}</strong>
                        <small>
                          {p.match_status.replaceAll("_", " ")} · confidence{" "}
                          {p.score.toFixed(2)} · similarity rank{" "}
                          {p.similarity_rank ?? "—"}
                        </small>
                      </span>
                      <span className="queueStatus">
                        {(
                          liveIncident
                            ? (bundle.review_events as any[]).some(
                                (e) => e.proposal_id === p.id,
                              )
                            : decisions.some(
                                (d) =>
                                  d.incident === bundle.incident.id &&
                                  d.proposal === p.id,
                              )
                        )
                          ? "Reviewed"
                          : "Open"}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="decision">
                  <h3>{proposal ? "Your review" : "Choose a queue item"}</h3>
                  {proposal ? (
                    <>
                      {liveIncident && (
                        <label className="region">
                          Final region (x1, y1, x2, y2)
                          <input
                            value={region}
                            onChange={(e) => setRegion(e.target.value)}
                            aria-label="Final region coordinates"
                          />
                        </label>
                      )}
                      <p>
                        {liveIncident
                          ? "Decisions are saved to the local workspace."
                          : "Visitor decisions stay in this browser."}
                      </p>
                      {liveIncident &&
                        flashEnabled &&
                        proposal.match_status === "cyclist_conflict" && (
                          <div>
                            <p>
                              Person / cyclist conflict: a second opinion can
                              describe the visible interaction. A reviewer still
                              decides.
                            </p>
                            <button
                              onClick={async () => {
                                const r = await fetch(
                                  `/api/incidents/${liveIncident}/flash`,
                                  {
                                    method: "POST",
                                    headers: {
                                      "Content-Type": "application/json",
                                    },
                                    body: JSON.stringify({
                                      proposal_id: proposal.id,
                                      manual: true,
                                    }),
                                  },
                                );
                                setFlashStatus(
                                  r.ok
                                    ? "Queued. Select Check opinion for status."
                                    : await r.text(),
                                );
                              }}
                            >
                              Ask Flash
                            </button>
                            <button
                              onClick={async () => {
                                const r = await fetch(
                                  `/api/incidents/${liveIncident}/flash/${proposal.id}`,
                                );
                                setFlashStatus(
                                  r.ok
                                    ? JSON.stringify(await r.json())
                                    : await r.text(),
                                );
                              }}
                            >
                              Check opinion
                            </button>
                            <p role="status">{flashStatus}</p>
                          </div>
                        )}
                      <div className="actions">
                        <button
                          className="primary"
                          onClick={() => decide("omission")}
                        >
                          Missed pedestrian <kbd>1</kbd>
                        </button>
                        <button onClick={() => decide("out_of_scope")}>
                          Out of scope <kbd>2</kbd>
                        </button>
                        <button onClick={() => decide("already_labeled")}>
                          Already labeled
                        </button>
                        <button onClick={() => decide("localization_error")}>
                          Box needs adjustment
                        </button>
                        <button onClick={() => decide("unresolved")}>
                          Needs another look
                        </button>
                      </div>
                      {current && (
                        <p className="saved">
                          {liveIncident
                            ? "Saved to workspace: "
                            : "Saved locally: "}
                          {labels[current.decision]}{" "}
                          <button
                            className="textbutton"
                            onClick={() => {
                              const history = liveIncident
                                ? liveEvents
                                : decisions.filter(
                                    (d) =>
                                      d.incident === bundle.incident.id &&
                                      d.proposal === proposal.id,
                                  );
                              decide(
                                history.length > 1
                                  ? history[history.length - 2].decision
                                  : "unresolved",
                              );
                            }}
                          >
                            Undo
                          </button>
                        </p>
                      )}
                    </>
                  ) : (
                    <p>Use the queue or arrow keys to inspect a suggestion.</p>
                  )}
                </div>
              </aside>
            </div>
          ) : view === "Audit" ? (
            liveIncident ? (
              <LiveAudit incident={liveIncident} />
            ) : (
              <section className="panel">
                <span className="overline">
                  Independent audit ·{" "}
                  {caseNo === 5 ? "synthetic fixture" : "seeded COCO release"}
                </span>
                <h2>Fixed sample, full-frame inspection</h2>
                <p>
                  {caseNo === 5
                    ? "This audit uses scripted fixture truth, not human review."
                    : "The sample is frozen for this COCO release. No independent auditors have reviewed it, so no completed prevalence estimate is available."}{" "}
                  Queue decisions never change this report.
                </p>
                {bundle.audit && (
                  <>
                    <div className="auditgrid">
                      <div>
                        <strong>{bundle.images.length}</strong>
                        <span>images in release</span>
                      </div>
                      <div>
                        <strong>
                          {bundle.audit.result.completed} /{" "}
                          {bundle.audit.result.sampled}
                        </strong>
                        <span>resolved inspections</span>
                      </div>
                      <div>
                        <strong>
                          {bundle.audit.result.status === "complete"
                            ? `${(bundle.audit.result.estimate * 100).toFixed(1)}%`
                            : "Unresolved"}
                        </strong>
                        <span>prevalence estimate</span>
                      </div>
                      <div>
                        <strong>
                          {bundle.audit.result.status === "complete"
                            ? `${(bundle.audit.result.lower * 100).toFixed(1)}–${(bundle.audit.result.upper * 100).toFixed(1)}%`
                            : `${(bundle.audit.result.all_unknown_negative.lower * 100).toFixed(1)}–${(bundle.audit.result.all_unknown_positive.upper * 100).toFixed(1)}%`}
                        </strong>
                        <span>
                          {bundle.audit.result.status === "complete"
                            ? "95% interval"
                            : "unresolved sensitivity envelope"}
                        </span>
                      </div>
                    </div>
                    <p>
                      Draw seed {bundle.audit.design.seed}; image unit; fixed
                      before decisions. Select a sampled frame:
                    </p>
                    <div className="filmstrip">
                      {bundle.audit.blind.images.map((i: any) => (
                        <button key={i.id} onClick={() => setAuditImage(i.id)}>
                          <img
                            src={
                              "./data/" +
                              bundle.images.find((x) => x.id === i.id)?.path
                            }
                            alt={"Inspect audit image " + i.id}
                          />
                          <span>Image {i.id}</span>
                        </button>
                      ))}
                    </div>
                    {auditImage && (
                      <img
                        className="auditframe"
                        src={
                          "./data/" +
                          bundle.images.find((x) => x.id === auditImage)?.path
                        }
                        alt={"Sampled full frame " + auditImage}
                      />
                    )}
                    <p>
                      Original labels:{" "}
                      {bundle.audit.blind.images.find(
                        (i: any) => i.id === auditImage,
                      )?.annotations.length || 0}
                      .
                    </p>
                    <a
                      href={`./data/${caseNo === 5 ? "case-0" : `photo-${caseNo}`}.json`}
                      download
                    >
                      Download audit evidence
                    </a>
                  </>
                )}
              </section>
            )
          ) : (
            <section className="panel">
              <span className="overline">Evidence report</span>
              <h2>Recorded investigation</h2>
              <p>
                {caseNo === 5
                  ? "This synthetic fixture uses scripted scenes and proposals."
                  : "This recorded COCO case uses original human annotations with seeded removals and RT-DETR proposals."}{" "}
                Visitor decisions are local and are not human study results.
              </p>
              <dl>
                <dt>Release</dt>
                <dd>{bundle.release.id}</dd>
                <dt>Incident</dt>
                <dd>{bundle.incident.id}</dd>
                <dt>Source</dt>
                <dd>
                  COCO 2017 validation; source attribution shown beside image
                </dd>
                <dt>Queue method</dt>
                <dd>Recorded detector and seed similarity fusion</dd>
                <dt>Independent audit</dt>
                <dd>Not completed</dd>
              </dl>
              <h3>Recorded review decisions</h3>
              {(bundle.review_events as any[]).length === 0 ? (
                <p>No recorded reviewer decisions for this investigation.</p>
              ) : (
                <ul>
                  {(bundle.review_events as any[]).map((event: any) => (
                    <li key={event.id}>
                      <button
                        className="textbutton"
                        onClick={() => {
                          const index = queue.findIndex(
                            (p) => p.id === event.proposal_id,
                          );
                          setSelected(index);
                          setView("Investigation");
                        }}
                      >
                        Image {event.image_id}
                      </button>
                      : {labels[event.decision]} · {event.actor_type} · event{" "}
                      {event.id.slice(0, 12)}
                    </li>
                  ))}
                </ul>
              )}
              <p>
                Visitor decisions are stored separately in this browser.{" "}
                <a href="https://github.com/JonathanKlees/rechecked">
                  ReChecked benchmark reference
                </a>
                ; documented fixture failures include signpost, rider conflict,
                localization shift and ignore region.
              </p>
              <p>
                Reproduce:{" "}
                <code>avtriage demo --workspace ./triage-workspace</code>
              </p>
              <a
                id="evidence"
                href={`./data/${caseNo === 5 ? "case-0" : `photo-${caseNo}`}.json`}
                download
              >
                Download replay JSON
              </a>
            </section>
          )}
          <footer>
            <div>
              <strong>Evidence, not an estimate.</strong> Seeded COCO
              annotations · recorded inference · no independent human pilot
            </div>
            <div>
              {!liveIncident && (
                <label>
                  Seed{" "}
                  <select
                    value={caseNo}
                    onChange={(e) => setCaseNo(Number(e.target.value))}
                  >
                    <option value={0}>Image 210273</option>
                    <option value={1}>Image 309391</option>
                    <option value={2}>Image 142472</option>
                    <option value={3}>Image 184324</option>
                    <option value={4}>Image 301376</option>
                    <option value={5}>Synthetic fixture</option>
                  </select>
                </label>
              )}
              {!liveIncident && (
                <button
                  onClick={() => {
                    setDecisions([]);
                  }}
                >
                  Reset visitor decisions
                </button>
              )}
              <span>← → navigate</span>
            </div>
          </footer>
        </main>
      )}
    </>
  );
}

const directAudit = new URLSearchParams(location.search).get("audit");
createRoot(document.getElementById("root")!).render(
  directAudit ? (
    <main>
      <LiveAudit incident="" initialDesign={directAudit} />
    </main>
  ) : (
    <App />
  ),
);
