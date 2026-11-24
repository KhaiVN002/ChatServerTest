import { useState, useRef, useEffect } from "react";
import "./App.css";

/* ---------- Icon nhỏ ---------- */
const paths = {
  panel: <><rect x="3.5" y="4.5" width="17" height="15" rx="3" /><path d="M9.5 4.5v15" /></>,
  edit: <><path d="M12 20h8" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4-4" /></>,
  graph: <><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="8" r="2.5" /><circle cx="9" cy="18" r="2.5" /><path d="M8.2 7l7.5.7M7.2 8.2l1 7.4M16.6 10.2l-5.5 6.1" /></>,
  db: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
  share: <><path d="M12 15V4M8 8l4-4 4 4" /><path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  up: <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" />,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2.5" /><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15" /></>,
  like: <path d="M7 11v9H4v-9ZM7 11l4-7c1.5 0 2.5 1 2.2 2.6L12.7 9H19a1.5 1.5 0 0 1 1.5 1.8l-1.2 7A2 2 0 0 1 17.3 19H7" />,
};
const Icon = ({ name, style }) => (
  <svg viewBox="0 0 24 24" style={style}>{paths[name]}</svg>
);

const SUGGESTIONS = [
  "Máy nào có số lần xác thực thất bại tăng đột biến?",
  "Máy nào kết nối tới nhiều máy đích bất thường?",
  "Máy nào khởi chạy nhiều tiến trình bất thường?",
];
const SRC_COLOR = { "auth.txt": "var(--siem)", "flows.txt": "var(--ids)", "proc.txt": "var(--edr)" };
const API_URL = "http://localhost:8080/chat";

async function askBackend(question) {
  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: question }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Backend lỗi " + res.status);
  }

  const data = await res.json();
  return {
    answer: data.reply,
    entities: data.entities || [],
    evidence: data.evidence || [],
    baseline: data.baseline,
    graph: data.graph || [],
  };
}

/* Biến `abc` trong câu trả lời thành <code> */
function renderAnswer(text) {
  return text.split(/(`[^`]+`)/g).map((part, i) =>
    part.startsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : part
  );
}

/* ---------- Các component ---------- */
function Composer({ value, onChange, onSend }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [value]);

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="composer">
      <button className="icon-btn" title="Đính kèm file log"><Icon name="plus" /></button>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Hỏi về xác thực thất bại, kết nối hoặc tiến trình tăng bất thường…"
      />
      <button className="send-button" onClick={onSend} disabled={!value.trim()} title="Gửi">
        <Icon name="up" />
      </button>
    </div>
  );
}

function BotMessage({ m }) {
  if (m.loading) return <div className="message bot"><span className="typing">Đang truy vấn log...</span></div>;
  if (m.error) return <div className="message bot"><p>Không lấy được dữ liệu: {m.error}</p></div>;
  return (
    <div className="message bot">
      <p>{renderAnswer(m.answer)}</p>

      {m.entities?.length > 0 && (
        <div className="entities">
          {m.entities.map((e, i) => (
            <span className="entity" key={i}><i>{e.type}</i> {e.value}</span>
          ))}
        </div>
      )}

      {m.baseline && (
        <div className="baseline-values" aria-label="So sánh baseline">
          <span>7 cửa sổ tham chiếu</span>
          <ol>
            {m.baseline.previous.map((value, index) => <li key={index}>{value}</li>)}
          </ol>
          <strong>Kiểm thử {m.baseline.current}</strong>
        </div>
      )}

      {m.graph?.length > 0 && (
        <details className="evidence graph-evidence" id={`graph-${m.id}`} open>
          <summary><span>Đồ thị bằng chứng</span><Icon name="chevron" /></summary>
          <ul className="graph-paths">
            {m.graph.map((event) => (
              <li key={event.id}>
                <code>{event.origin}</code><span aria-hidden="true">→</span>
                <span className="graph-event">
                  {event.label}<small>{event.time}{event.detail && ` · ${event.detail}`}</small>
                </span>
                <span aria-hidden="true">→</span><code>{event.target}</code>
              </li>
            ))}
          </ul>
        </details>
      )}

      {m.evidence?.length > 0 && (
        <details className="evidence" open>
          <summary>
            <span>Bằng chứng ({m.evidence.length} bản ghi)</span>
            <Icon name="chevron" />
          </summary>
          <div className="log">
            {m.evidence.map((ev, i) => (
              <div key={i} style={{ display: "contents" }}>
                <span className="src" style={{ color: SRC_COLOR[ev.source] }}>{ev.source}</span>
                <code title={`Byte ${ev.offset} trong ${ev.source}`}><span className="t">{ev.time}</span> {ev.line}</code>
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="actions">
        <button className="icon-btn" title="Sao chép"><Icon name="copy" /></button>
        <button className="icon-btn" title="Hữu ích"><Icon name="like" /></button>
        <button className="icon-btn" title="Chưa đúng"><Icon name="like" style={{ transform: "scaleY(-1)" }} /></button>
      </div>
    </div>
  );
}

/* ---------- App ---------- */
export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const chatRef = useRef(null);
  const nextMessage = useRef(0);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q) return;
    const id = nextMessage.current++;
    setInput("");
    setMessages((m) => [...m, { id, role: "user", text: q }, { id, role: "bot", loading: true }]);

    let reply;
    try {
      reply = { role: "bot", ...(await askBackend(q)) };
    } catch (err) {
      reply = { role: "bot", error: err.message };
    }
    setMessages((m) => m.map((msg) => msg.id === id && msg.role === "bot" ? { ...reply, id } : msg));
  }

  const started = messages.length > 0;
  const latestGraph = messages.findLast((m) => m.graph?.length);

  function showGraph() {
    const graph = document.getElementById(`graph-${latestGraph?.id}`);
    if (graph) {
      graph.open = true;
      graph.scrollIntoView({ block: "nearest" });
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="brand">metroAsist</span>
          <button className="icon-btn" title="Ẩn thanh bên"><Icon name="panel" /></button>
        </div>

        <nav className="nav">
          <button className="nav-item active" onClick={() => setMessages([])}><Icon name="edit" />Cuộc điều tra mới</button>
          <button className="nav-item" onClick={showGraph} disabled={!latestGraph}><Icon name="graph" />Đồ thị sự kiện</button>
        </nav>

        <div className="section-title">Câu hỏi mẫu</div>
        <div className="history">
          {SUGGESTIONS.map((question) => (
            <button key={question} className="history-item" onClick={() => send(question)}>{question}</button>
          ))}
        </div>

        <div className="profile">
          <div className="avatar">K</div>
          <div><b>Kỹ sư SOC</b><small>Ca trực đêm</small></div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="model-btn">metroAsist <Icon name="chevron" /></button>
          <button className="share-btn"><Icon name="share" />Chia sẻ</button>
        </header>

        <div className="chat-area" ref={chatRef}>
          {!started ? (
            <div className="welcome">
              <h1>Hôm nay bạn muốn điều tra gì?</h1>
              <div className="input-wrap">
                <Composer value={input} onChange={setInput} onSend={() => send()} />
              </div>

              <div className="source-row">
                <span><span className="dot" style={{ background: "var(--siem)" }} />Xác thực</span>
                <span><span className="dot" style={{ background: "var(--ids)" }} />Luồng mạng</span>
                <span><span className="dot" style={{ background: "var(--edr)" }} />Tiến trình</span>
              </div>

              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="suggestion" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((m) =>
                m.role === "user"
                  ? <div key={`user-${m.id}`} className="message user">{m.text}</div>
                  : <BotMessage key={`bot-${m.id}`} m={m} />
              )}
            </div>
          )}
        </div>

        {started && (
          <>
            <div className="input-wrap">
              <Composer value={input} onChange={setInput} onSend={() => send()} />
            </div>
            <div className="disclaimer">Mẫu LANL · Thời gian tính bằng giây tương đối trong dataset.</div>
          </>
        )}
      </div>
    </div>
  );
}
