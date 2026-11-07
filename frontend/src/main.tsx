import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { pct } from "./display";
import "./styles.css";
type Compound = { name: string; smiles: string; identifiers: unknown[] };
type Condition = { label: string; value: unknown; original: unknown };
type RecordRow = {
  id: string;
  group_id: string;
  source_row: number;
  yield_value: number | null;
  conditions: Record<string, Condition>;
  substrates: Compound[];
  products: Compound[];
  primary_measurement: unknown;
  diagnostics: string[];
  measurements: unknown[];
};
type Group = {
  id: string;
  count: number;
  usable: number;
  minimum: number;
  maximum: number;
  median: number;
  stddev: number;
  spread: number;
  substrates: Compound[];
  products: Compound[];
  dimensions: Record<string, string[]>;
};
type Pair = {
  reaction_ids: string[];
  delta: number;
  factor?: string;
  count?: number;
};
type Insights = {
  single_factor: Pair[];
  same_conditions: Pair[];
  extremes: Pair | null;
};
type Comparison = {
  a: RecordRow;
  b: RecordRow;
  delta_percentage_points: number | null;
  classification: string;
  matrix: { field: string; a: string; b: string; status: string }[];
  explanation: string;
  matches: string[];
  differences: string[];
  missing: string[];
};
type Distribution = {
  count: number;
  usable: number;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  histogram: { bin: string; count: number }[];
  by_condition: {
    label: string;
    count: number;
    median: number;
    minimum: number;
    maximum: number;
    q1: number;
    q3: number;
  }[];
};
async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch("/api" + path, { signal });
  if (!r.ok) {
    const e = await r.json();
    throw new Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
const short = (s: string, n = 32) =>
  s.length > n ? s.slice(0, n - 1) + "…" : s;
const label = (s: string) => s.replaceAll("_", " ");
const filtersList = [
  "catalyst",
  "ligand",
  "base",
  "solvent",
  "temperature",
  "duration",
];
export function Molecule({ c, role }: { c: Compound; role: string }) {
  return (
    <div className="molecule">
      <span className="eyebrow">{role}</span>
      <img
        alt={`Molecular structure: ${c.name}`}
        src={"/api/structure?smiles=" + encodeURIComponent(c.smiles)}
      />
      <strong>{c.name === c.smiles ? "Intended C–N product" : c.name}</strong>
      <details>
        <summary>Structural identifier</summary>
        <code>{c.smiles}</code>
      </details>
    </div>
  );
}
function App() {
  const [groups, setGroups] = useState<Group[]>([]),
    [gid, setGid] = useState(""),
    [group, setGroup] = useState<Group | null>(null),
    [rows, setRows] = useState<RecordRow[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(0),
    [filters, setFilters] = useState<Record<string, string>>({}),
    [sort, setSort] = useState("yield_value"),
    [direction, setDirection] = useState("desc"),
    [dimension, setDimension] = useState("catalyst"),
    [distribution, setDistribution] = useState<Distribution | null>(null),
    [selected, setSelected] = useState<string[]>([]),
    [comparison, setComparison] = useState<Comparison | null>(null),
    [insight, setInsight] = useState<Insights | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(true),
    [tab, setTab] = useState("explore"),
    [detail, setDetail] = useState<RecordRow | null>(null),
    [dataset, setDataset] = useState<any>(null),
    [groupSort, setGroupSort] = useState("spread");
  useEffect(() => {
    const ctl = new AbortController();
    api<any>("/groups?sort=" + groupSort, ctl.signal)
      .then((d) => {
        setGroups(d.items);
        setGid((id) => id || d.items[0]?.id || "");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    api("/dataset", ctl.signal)
      .then(setDataset)
      .catch(() => {});
    return () => ctl.abort();
  }, [groupSort]);
  useEffect(() => {
    if (!gid) return;
    const ctl = new AbortController();
    setGroup(null);
    setSelected([]);
    setComparison(null);
    setInsight(null);
    setFilters({});
    setPage(0);
    api<Group>("/groups/" + gid, ctl.signal)
      .then(setGroup)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    api<Insights>("/groups/" + gid + "/insights", ctl.signal)
      .then(setInsight)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctl.abort();
  }, [gid]);
  const query = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v),
  ).toString();
  useEffect(() => {
    if (!group || group.id !== gid) return;
    const ctl = new AbortController();
    setBusy(true);
    setError("");
    setDistribution(null);
    Promise.all([
      api<any>(
        `/groups/${gid}/reactions?${query}&sort=${sort}&direction=${direction}&offset=${page * 25}`,
        ctl.signal,
      ),
      api<Distribution>(
        `/groups/${gid}/distribution?${query}&dimension=${dimension}`,
        ctl.signal,
      ),
    ])
      .then(([r, d]) => {
        setRows(r.items);
        setTotal(r.total);
        setDistribution(d);
        setBusy(false);
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setError(e.message);
          setBusy(false);
        }
      });
    return () => ctl.abort();
  }, [gid, group, query, page, sort, direction, dimension]);
  useEffect(() => {
    setComparison(null);
    if (selected.length !== 2) return;
    const ctl = new AbortController();
    api<Comparison>("/compare?reaction_ids=" + selected.join(","), ctl.signal)
      .then(setComparison)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctl.abort();
  }, [selected]);
  function select(id: string) {
    setSelected((s) =>
      s.includes(id)
        ? s.filter((i) => i !== id)
        : s.length < 2
          ? [...s, id]
          : [s[1], id],
    );
  }
  function candidate(p: Pair) {
    setSelected(p.reaction_ids);
    setTimeout(
      () =>
        document
          .getElementById("comparison")
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
      50,
    );
  }
  function changeFilter(f: string, v: string) {
    setFilters((s) => ({ ...s, [f]: v }));
    setPage(0);
  }
  return (
    <>
      <header>
        <a className="brand" href="#" onClick={() => setTab("explore")}>
          <span className="brand-icon">
            R<span>v</span>
          </span>
          <span>
            Reaction<span className="light">Variance</span>
            <small>EXPERIMENTAL EVIDENCE EXPLORER</small>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <button
            className={tab === "explore" ? "active" : ""}
            onClick={() => setTab("explore")}
          >
            Explore reactions
          </button>
          <button
            className={tab === "method" ? "active" : ""}
            onClick={() => setTab("method")}
          >
            Data & methodology
          </button>
          <a href="/docs" target="_blank" rel="noreferrer">
            API ↗
          </a>
        </nav>
        <span className="local">
          <i /> LOCAL DATASET
        </span>
      </header>
      <main>
        <div className="topline">
          <span>OPEN REACTION DATABASE / C–N COUPLING</span>
          <span>
            STUDY 01 <b>·</b> 50,688 EXPERIMENTS
          </span>
        </div>
        {error && (
          <div role="alert" className="error">
            {error}
            <br />
            <small>
              For a missing dataset, run{" "}
              <code>make download && make ingest</code>, then reload.
            </small>
          </div>
        )}
        {tab === "method" ? (
          <Methodology dataset={dataset} />
        ) : (
          <>
            <section className="intro">
              <div>
                <div className="eyebrow">
                  SAME MOLECULES. DIFFERENT OUTCOMES.
                </div>
                <h1>Inspect the difference.</h1>
                <p>
                  Compare published experiments with the same substrates and
                  intended product.
                  <br />
                  Follow the reported yields. Examine the recorded conditions.
                </p>
              </div>
              <div className="study-note">
                <span className="eyebrow">SOURCE STUDY</span>
                <p>
                  50,688 Pd-, Ni- and Cu-catalysed
                  <br />
                  C–N coupling experiments
                </p>
                <a
                  href="https://doi.org/10.1021/jacs.6c05959"
                  target="_blank"
                  rel="noreferrer"
                >
                  View publication ↗
                </a>
              </div>
            </section>
            <div className="workspace">
              <aside>
                <div className="aside-heading">
                  <span className="eyebrow">REACTION GROUPS</span>
                  <span className="badge">{groups.length}</span>
                </div>
                <p className="muted">Strict substrate + product match</p>
                <label className="sort-label">
                  Order groups
                  <select
                    value={groupSort}
                    onChange={(e) => setGroupSort(e.target.value)}
                  >
                    <option value="spread">Largest yield range</option>
                    <option value="count">Most experiments</option>
                    <option value="stddev">Highest standard deviation</option>
                    <option value="usable">Most usable yields</option>
                  </select>
                </label>
                <div className="group-list">
                  {groups.map((g, i) => (
                    <button
                      key={g.id}
                      className={"group-card " + (gid === g.id ? "chosen" : "")}
                      onClick={() => setGid(g.id)}
                    >
                      <span className="group-number">
                        0{i + 1} <span>→</span>
                      </span>
                      <strong>
                        {g.substrates.map((c) => c.name).join(" + ")}
                      </strong>
                      <span className="group-meta">
                        {g.count.toLocaleString()} experiments
                      </span>
                      <div className="range-track">
                        <span
                          style={{
                            left: g.minimum + "%",
                            width: g.maximum - g.minimum + "%",
                          }}
                        />
                      </div>
                      <span className="range-label">
                        {pct(g.minimum)} <span>—</span> {pct(g.maximum)}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="aside-note">
                  <span>ⓘ</span>
                  <p>
                    Exact molecular identities.
                    <br />
                    Recorded differences.
                    <br />
                    No causal claims.
                  </p>
                </div>
              </aside>
              <div className="content">
                {group ? (
                  <>
                    <section className="panel reaction-panel">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">SELECTED REACTION</span>
                          <h2>A shared chemical starting point</h2>
                        </div>
                        <span className="pill">STRICT MATCH</span>
                      </div>
                      <div className="reaction-scheme">
                        {group.substrates.map((c, i) => (
                          <React.Fragment key={c.smiles}>
                            {i > 0 && (
                              <span className="reaction-symbol">+</span>
                            )}
                            <Molecule c={c} role={"SUBSTRATE " + (i + 1)} />
                          </React.Fragment>
                        ))}
                        <div className="reaction-arrow">
                          C–N coupling<span>⟶</span>
                        </div>
                        {group.products.map((c) => (
                          <Molecule
                            key={c.smiles}
                            c={c}
                            role="INTENDED PRODUCT"
                          />
                        ))}
                      </div>
                      <div className="stats">
                        <div>
                          <strong>{group.count.toLocaleString()}</strong>
                          <span>matched experiments</span>
                        </div>
                        <div>
                          <strong>
                            {pct(group.minimum)}–{pct(group.maximum)}
                          </strong>
                          <span>valid reported yield range</span>
                        </div>
                        <div>
                          <strong>{pct(group.median)}</strong>
                          <span>median reported yield</span>
                        </div>
                        <div>
                          <strong>
                            {group.stddev.toFixed(1)} <small>pp</small>
                          </strong>
                          <span>sample standard deviation</span>
                        </div>
                      </div>
                    </section>
                    <section className="panel evidence">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">
                            01 / OBSERVED VARIATION
                          </span>
                          <h2>Reported assay yields</h2>
                        </div>
                        <a
                          className="text-link"
                          href={`/api/export?group_id=${gid}&${query}`}
                        >
                          Export filtered group ↓
                        </a>
                      </div>
                      <div className="filters">
                        {filtersList
                          .filter((f) => group.dimensions[f].length > 1)
                          .map((f) => (
                            <label key={f}>
                              {label(f)}
                              <select
                                aria-label={`Filter ${f}`}
                                value={filters[f] || ""}
                                onChange={(e) =>
                                  changeFilter(f, e.target.value)
                                }
                              >
                                <option value="">All {f} values</option>
                                {group.dimensions[f].map((v) => (
                                  <option key={v} value={v}>
                                    {short(v, 65)}
                                  </option>
                                ))}
                              </select>
                            </label>
                          ))}
                        <label>
                          Yield ≥ %
                          <input
                            aria-label="Minimum yield"
                            type="number"
                            min="0"
                            max="100"
                            value={filters.yield_min || ""}
                            onChange={(e) =>
                              changeFilter("yield_min", e.target.value)
                            }
                          />
                        </label>
                        <label>
                          Yield ≤ %
                          <input
                            aria-label="Maximum yield"
                            type="number"
                            min="0"
                            max="100"
                            value={filters.yield_max || ""}
                            onChange={(e) =>
                              changeFilter("yield_max", e.target.value)
                            }
                          />
                        </label>
                        <button
                          className="reset"
                          onClick={() => {
                            setFilters({});
                            setPage(0);
                          }}
                        >
                          Reset
                        </button>
                      </div>
                      <div className="chart-summary" aria-live="polite">
                        {busy ? (
                          "Loading filtered observations…"
                        ) : (
                          <>
                            <b>{distribution?.count.toLocaleString()}</b>{" "}
                            filtered experiments <span>·</span>{" "}
                            <b>{distribution?.usable.toLocaleString()}</b> valid
                            yields <span>·</span> median{" "}
                            <b>{pct(distribution?.median)}</b>
                          </>
                        )}
                      </div>
                      <div className="charts">
                        <div>
                          <h3>Yield distribution</h3>
                          <p className="muted">
                            All valid filtered measurements · 10
                            percentage-point bins
                          </p>
                          <div
                            className="chart"
                            role="img"
                            aria-label="Histogram of filtered reported yields"
                          >
                            <ResponsiveContainer width="100%" height={225}>
                              <BarChart
                                data={distribution?.histogram || []}
                                margin={{
                                  left: 5,
                                  right: 16,
                                  top: 15,
                                  bottom: 15,
                                }}
                              >
                                <CartesianGrid
                                  vertical={false}
                                  stroke="#e7e9e4"
                                />
                                <XAxis
                                  dataKey="bin"
                                  tick={{ fontSize: 10 }}
                                  label={{
                                    value: "Reported assay yield (%)",
                                    position: "bottom",
                                    offset: 0,
                                    fontSize: 11,
                                  }}
                                />
                                <YAxis tick={{ fontSize: 10 }} width={45} />
                                <Tooltip />
                                <Bar
                                  dataKey="count"
                                  name="Experiments"
                                  fill="#286858"
                                  radius={[3, 3, 0, 0]}
                                />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                        <div>
                          <div className="condition-heading">
                            <h3>Yield by recorded condition</h3>
                            <select
                              aria-label="Chart condition"
                              value={dimension}
                              onChange={(e) => setDimension(e.target.value)}
                            >
                              {filtersList
                                .filter((f) => group.dimensions[f].length > 1)
                                .map((f) => (
                                  <option key={f} value={f}>
                                    {label(f)}
                                  </option>
                                ))}
                            </select>
                          </div>
                          <p className="muted">
                            Median and full range · each row is a category
                          </p>
                          <div
                            className="condition-chart"
                            role="img"
                            aria-label={`Yield ranges by ${dimension}`}
                          >
                            <ResponsiveContainer
                              width="100%"
                              height={Math.max(
                                225,
                                (distribution?.by_condition.length || 0) * 31,
                              )}
                            >
                              <ScatterChart
                                margin={{
                                  left: 5,
                                  right: 26,
                                  top: 15,
                                  bottom: 20,
                                }}
                              >
                                <CartesianGrid
                                  horizontal={false}
                                  stroke="#e7e9e4"
                                />
                                <XAxis
                                  type="number"
                                  dataKey="median"
                                  domain={[0, 100]}
                                  unit="%"
                                  tick={{ fontSize: 10 }}
                                />
                                <YAxis
                                  type="category"
                                  dataKey="label"
                                  width={106}
                                  tick={{ fontSize: 10 }}
                                  tickFormatter={(s) => short(s, 17)}
                                  allowDuplicatedCategory={false}
                                />
                                <Tooltip
                                  content={({ active, payload }) =>
                                    active && payload?.length ? (
                                      <div className="chart-tip">
                                        <b>{payload[0].payload.label}</b>
                                        <br />
                                        n={payload[0].payload.count}; median{" "}
                                        {pct(payload[0].payload.median)}
                                        <br />
                                        Range {pct(payload[0].payload.minimum)}–
                                        {pct(payload[0].payload.maximum)}
                                      </div>
                                    ) : null
                                  }
                                />
                                <Scatter
                                  data={(distribution?.by_condition || []).map(
                                    (c) => ({
                                      ...c,
                                      error: [
                                        c.median - c.minimum,
                                        c.maximum - c.median,
                                      ],
                                    }),
                                  )}
                                  fill="#b36c42"
                                >
                                  <ErrorBar
                                    dataKey="error"
                                    direction="x"
                                    width={3}
                                    stroke="#b36c42"
                                  />
                                </Scatter>
                              </ScatterChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      </div>
                      <p className="footnote">
                        Analytical yields, not predictions. Flagged values
                        outside 0–100% are excluded. Associations do not
                        establish causation.
                      </p>
                    </section>
                    <section className="panel">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">
                            02 / EXPERIMENT RECORDS
                          </span>
                          <h2>Choose two. Examine what changed.</h2>
                        </div>
                        <span className="selection-count">
                          {selected.length}/2 selected{" "}
                          <button onClick={() => setSelected([])}>Clear</button>
                        </span>
                      </div>
                      <div className="table-tools">
                        <span className="muted">
                          Selections persist across pages within this group.
                        </span>
                        <label>
                          Sort{" "}
                          <select
                            aria-label="Sort experiments"
                            value={sort}
                            onChange={(e) => {
                              setSort(e.target.value);
                              setPage(0);
                            }}
                          >
                            <option value="yield_value">Reported yield</option>
                            {filtersList.map((f) => (
                              <option key={f} value={f}>
                                {label(f)}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          onClick={() =>
                            setDirection((d) => (d === "desc" ? "asc" : "desc"))
                          }
                        >
                          {direction === "desc"
                            ? "↓ Descending"
                            : "↑ Ascending"}
                        </button>
                      </div>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th scope="col">Select</th>
                              <th scope="col">ORD experiment</th>
                              <th scope="col">Yield</th>
                              {filtersList.map((f) => (
                                <th scope="col" key={f}>
                                  {label(f)}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {!busy && rows.length === 0 && (
                              <tr>
                                <td colSpan={9}>
                                  No experiments match these filters. Adjust or
                                  reset the filters.
                                </td>
                              </tr>
                            )}
                            {rows.map((r) => (
                              <tr
                                key={r.id}
                                className={
                                  selected.includes(r.id) ? "selected" : ""
                                }
                              >
                                <td>
                                  <input
                                    type="checkbox"
                                    aria-label={`Select ${r.id}`}
                                    checked={selected.includes(r.id)}
                                    onChange={() => select(r.id)}
                                  />
                                </td>
                                <td>
                                  <button
                                    className="record-link"
                                    title={r.id}
                                    onClick={() =>
                                      api<RecordRow>("/reactions/" + r.id)
                                        .then(setDetail)
                                        .catch((e) => setError(e.message))
                                    }
                                  >
                                    {r.id.slice(0, 12)}… ↗
                                  </button>
                                  <small>source row {r.source_row}</small>
                                </td>
                                <td className="yield">
                                  {pct(r.yield_value)}
                                  {r.diagnostics.length > 0 && (
                                    <span title={r.diagnostics.join(", ")}>
                                      {" "}
                                      ⚑
                                    </span>
                                  )}
                                </td>
                                {filtersList.map((f) => (
                                  <td key={f} title={r.conditions[f].label}>
                                    {short(r.conditions[f].label, 27)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="pagination">
                        <span>
                          {total
                            ? `${page * 25 + 1}–${Math.min((page + 1) * 25, total)} of ${total.toLocaleString()}`
                            : "0 experiments"}
                        </span>
                        <div>
                          <button
                            disabled={page === 0 || busy}
                            onClick={() => setPage((p) => p - 1)}
                          >
                            ← Previous
                          </button>
                          <button
                            disabled={(page + 1) * 25 >= total || busy}
                            onClick={() => setPage((p) => p + 1)}
                          >
                            Next →
                          </button>
                        </div>
                      </div>
                    </section>
                    <section className="panel candidate-panel">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">
                            EVIDENCE-DRIVEN STARTING POINTS
                          </span>
                          <h2>Look closer at a contrast</h2>
                        </div>
                        <span className="muted">
                          Calculated from the whole group
                        </span>
                      </div>
                      <div className="candidates">
                        {insight?.single_factor.slice(0, 3).map((p, i) => (
                          <button key={i} onClick={() => candidate(p)}>
                            <span className="eyebrow">ONE RECORDED FACTOR</span>
                            <strong>
                              {p.delta.toFixed(1)} <small>pp difference</small>
                            </strong>
                            <span>
                              Different {p.factor} <b>↗</b>
                            </span>
                          </button>
                        ))}
                        {insight && insight.single_factor.length === 0 && (
                          <p>
                            No complete single recorded-factor contrasts found.
                          </p>
                        )}
                        {insight?.extremes && (
                          <button onClick={() => candidate(insight.extremes!)}>
                            <span className="eyebrow">LOWEST ↔ HIGHEST</span>
                            <strong>
                              {insight.extremes.delta?.toFixed(1) ?? "—"}{" "}
                              <small>pp spread</small>
                            </strong>
                            <span>
                              Inspect all recorded differences <b>↗</b>
                            </span>
                          </button>
                        )}
                      </div>
                      {insight?.same_conditions[0] && (
                        <button
                          className="replicate"
                          onClick={() => candidate(insight.same_conditions[0])}
                        >
                          Same recorded conditions: inspect a{" "}
                          {insight.same_conditions[0].delta.toFixed(1)} pp
                          spread across {insight.same_conditions[0].count}{" "}
                          observations ↗
                        </button>
                      )}
                    </section>
                    <section id="comparison" className="panel comparison">
                      <div className="section-heading">
                        <div>
                          <span className="eyebrow">
                            03 / COMPARISON WORKSPACE
                          </span>
                          <h2>The evidence, side by side.</h2>
                        </div>
                        {comparison && (
                          <a
                            className="text-link"
                            href={
                              "/api/export?reaction_ids=" + selected.join(",")
                            }
                          >
                            Export comparison ↓
                          </a>
                        )}
                      </div>
                      {comparison ? (
                        <>
                          <div className="comparison-yields">
                            <div>
                              <span className="eyebrow">EXPERIMENT A</span>
                              <strong>{pct(comparison.a.yield_value)}</strong>
                              <code>{comparison.a.id}</code>
                              <div className="yield-bar">
                                <span
                                  style={{
                                    width:
                                      (comparison.a.yield_value || 0) + "%",
                                  }}
                                />
                              </div>
                            </div>
                            <div className="delta">
                              <strong>
                                {comparison.delta_percentage_points == null
                                  ? "Unavailable"
                                  : `${comparison.delta_percentage_points >= 0 ? "+" : ""}${comparison.delta_percentage_points.toFixed(1)}`}
                              </strong>
                              <span>percentage points · B − A</span>
                              <b>{label(comparison.classification)}</b>
                            </div>
                            <div>
                              <span className="eyebrow">EXPERIMENT B</span>
                              <strong>{pct(comparison.b.yield_value)}</strong>
                              <code>{comparison.b.id}</code>
                              <div className="yield-bar second">
                                <span
                                  style={{
                                    width:
                                      (comparison.b.yield_value || 0) + "%",
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                          <div className="table-scroll">
                            <table className="difference-matrix">
                              <thead>
                                <tr>
                                  <th>Recorded factor</th>
                                  <th>Experiment A</th>
                                  <th>Status</th>
                                  <th>Experiment B</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <th>Substrates + product</th>
                                  <td>Same canonical molecular identities</td>
                                  <td>✓ match</td>
                                  <td>Same canonical molecular identities</td>
                                </tr>
                                {comparison.matrix.map((m) => (
                                  <tr className={m.status} key={m.field}>
                                    <th>{label(m.field)}</th>
                                    <td>{m.a}</td>
                                    <td>
                                      {m.status === "match"
                                        ? "✓"
                                        : m.status === "differ"
                                          ? "≠"
                                          : "?"}{" "}
                                      {m.status}
                                    </td>
                                    <td>{m.b}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <p className="interpretation">
                            {comparison.explanation}
                          </p>
                          <p className="footnote">
                            Tracked factors include quantities and full solvent
                            inventory. Setup and unrecorded variables may still
                            differ.{" "}
                            <button
                              className="inline"
                              onClick={() => setTab("method")}
                            >
                              Read comparison rules ↗
                            </button>
                          </p>
                        </>
                      ) : (
                        <div className="empty-comparison">
                          <span>⇄</span>
                          <h3>
                            {selected.length === 2
                              ? "Loading comparison…"
                              : "A useful comparison begins with two experiments."}
                          </h3>
                          <p>
                            Select two records in the table, or open a contrast
                            above.
                          </p>
                        </div>
                      )}
                    </section>
                  </>
                ) : (
                  <div className="panel loading">
                    {error
                      ? "Dataset setup required. See the instructions above."
                      : "Reading local reaction groups…"}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
        <footer>
          <span>
            ReactionVariance <b>·</b> Evidence before interpretation.
          </span>
          <span>
            ORD data · CC-BY-SA-4.0 <b> / </b> Code · MIT
          </span>
        </footer>
      </main>
      {detail && (
        <dialog
          ref={(el) => {
            if (el && !el.open) el.showModal();
          }}
          className="modal"
          aria-labelledby="record-title"
          onCancel={() => setDetail(null)}
        >
          <button autoFocus className="close" onClick={() => setDetail(null)}>
            Close ×
          </button>
          <span className="eyebrow">SOURCE RECORD</span>
          <h2 id="record-title">{detail.id}</h2>
          <p>
            Reported primary yield: <b>{pct(detail.yield_value)}</b> · Source
            row {detail.source_row}
          </p>
          <p>
            {detail.diagnostics.length
              ? "Quality flags: " + detail.diagnostics.join(", ")
              : "No extraction quality flags"}
          </p>
          <p>
            <a
              href="https://doi.org/10.1021/jacs.6c05959"
              target="_blank"
              rel="noreferrer"
            >
              Source publication ↗
            </a>
          </p>
          <details open>
            <summary>Measurement provenance and original fields</summary>
            <pre>{JSON.stringify(detail, null, 2)}</pre>
          </details>
        </dialog>
      )}
    </>
  );
}
function Methodology({ dataset }: { dataset: any }) {
  return (
    <article className="method panel">
      <span className="eyebrow">DATA & METHODOLOGY</span>
      <h1>Transparent by construction.</h1>
      <p>
        ReactionVariance compares reported experimental evidence. It does not
        predict yields, recommend conditions, or establish causes.
      </p>
      <h2>A published C–N coupling screen</h2>
      <p>
        <a href="https://doi.org/10.1021/jacs.6c05959">
          A 50,688-Reaction Data Set Reveals General Ligands and Mechanistic
          Diversity in C–N Couplings ↗
        </a>
        . Source: Open Reaction Database. Analytical yields are calibrated
        desired-product YIELD measurements associated with LCMS analyses, rather
        than isolated preparative yields.
      </p>
      <h2>Exact structure matching</h2>
      <p>
        RDKit canonical isomeric SMILES identify two explicit REACTANT
        substrates and a unique desired product. Stereochemistry, isotopes,
        charges, counterions and salts are retained. Catalysts, ligands and
        solvents never enter the substrate key. Unknown or ambiguous identities
        cannot create strict groups.
      </p>
      <h2>What counts as a recorded factor?</h2>
      <p>
        We compare substrate quantities, catalyst, ligand, base, the full
        solvent inventory, temperature, duration, pressure/atmosphere, stirring,
        and other recorded inputs. Component factors include quantities. Both
        metal catalysts and ligands are marked CATALYST in the source; explicit
        input names plus dataset custom role codes distinguish them. No
        extraction depends on ingredient order.
      </p>
      <p>
        Temperature converts to °C and outcome reaction time to hours. Component
        amounts preserve source units. “Explicitly none” requires an explicit
        source absence code. Missing values remain unavailable. Unknown never
        matches unknown. Unrecorded experimental setup may still differ.
      </p>
      <h2>Yield selection and quality</h2>
      <p>
        Only desired-product YIELD measurements with percentage values qualify.
        Zero remains zero; missing never becomes zero. AREA measurements and
        side-product yields are excluded. Where multiple measurements exist,
        selection prefers latest known reaction time, then authentic-standard
        calibration, then stable source order. All measurement provenance
        remains inspectable.
      </p>
      <p>
        Out-of-range values are flagged and preserved, never clipped. They are
        excluded from statistics and charts. Standard deviation uses n−1.
        Comparisons with incompatible assay metadata are incomplete, with no
        percentage-point contrast.
      </p>
      <h2>Comparison rules</h2>
      <ul>
        <li>
          All tracked factors known and matching: exact recorded conditions.
        </li>
        <li>All tracked factors known, one differs: single recorded factor.</li>
        <li>
          All tracked factors known, two or more differ: multiple recorded
          factors.
        </li>
        <li>
          Any tracked factor missing, or yield methods incompatible: incomplete.
        </li>
      </ul>
      <p>
        Candidate contrasts use condition signatures with one omitted factor,
        avoiding a quadratic all-pairs scan. Charts summarize every valid
        filtered yield; categorical plots show each category’s median and full
        observed range. The suggested contrasts use the entire selected group.
      </p>
      <h2>Interpretation has limits</h2>
      <p>
        Assay calibration, measurement technique, unrecorded variables and
        confounding affect results. A single recorded-factor contrast does not
        establish a controlled experiment or causation. Identical recorded
        conditions do not prove independent laboratory replication or physically
        identical experiments. A large yield spread alone does not quantify
        reproducibility.
      </p>
      <h2>Provenance & licensing</h2>
      <p>
        Data and derived exports:{" "}
        <a href="https://creativecommons.org/licenses/by-sa/4.0/">
          CC-BY-SA-4.0
        </a>
        , attributed to ORD and the source study authors. Software: MIT. No
        source data is relicensed by the software license. All records retain
        their original ORD IDs and local source row references.
      </p>
      {dataset && (
        <>
          <dl>
            <dt>Dataset ID</dt>
            <dd>{dataset.dataset_id}</dd>
            <dt>Source checksum · SHA-256</dt>
            <dd>{dataset.sha256}</dd>
            <dt>Imported UTC</dt>
            <dd>{dataset.imported_at}</dd>
            <dt>Records / strict groups / usable yields</dt>
            <dd>
              {dataset.audit.record_count.toLocaleString()} /{" "}
              {dataset.audit.comparable_groups} /{" "}
              {dataset.audit.usable_yields.toLocaleString()}
            </dd>
            <dt>Quality exclusions</dt>
            <dd>{JSON.stringify(dataset.audit.diagnostics)}</dd>
          </dl>
          <a href={dataset.source_url}>Original Parquet download ↗</a>
          <details>
            <summary>Full audit and parser versions</summary>
            <pre>{JSON.stringify(dataset, null, 2)}</pre>
          </details>
        </>
      )}
    </article>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
