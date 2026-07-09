import { useState } from 'react';

const API_URL = 'http://localhost:8000';

function App() {
  const [question, setQuestion] = useState('');
  const [template, setTemplate] = useState('support');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I can help you analyze customer complaints and propose support actions. Try asking about billing, delivery delays, refunds, or product defects.',
    },
  ]);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');

  const askQuestion = async () => {
    if (!question.trim()) return;
    const userMessage = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const params = new URLSearchParams({ question, template });
      const res = await fetch(`${API_URL}/ask?${params.toString()}`);
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer || 'No answer returned' }]);
      setSources(data.sources || []);
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'The assistant could not reach the service. Please try again.' }]);
    } finally {
      setLoading(false);
      setQuestion('');
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
      const data = await res.json();
      setUploadMessage(`Uploaded ${file.name}: ${data.status}`);
    } catch (error) {
      setUploadMessage('Upload failed.');
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a, #1e293b)', color: 'white', fontFamily: 'Inter, Arial, sans-serif' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ marginBottom: 8 }}>Complaint RAG Assistant</h1>
          <p style={{ margin: 0, color: '#cbd5e1' }}>Ask about customer complaints, retrieve similar cases, and generate support-ready responses.</p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20 }}>
          <aside style={{ background: 'rgba(15, 23, 42, 0.75)', border: '1px solid #334155', borderRadius: 16, padding: 16 }}>
            <h3 style={{ marginTop: 0 }}>Controls</h3>
            <label style={{ display: 'block', marginBottom: 8 }}>Prompt template</label>
            <select value={template} onChange={(e) => setTemplate(e.target.value)} style={{ width: '100%', padding: 10, borderRadius: 8, marginBottom: 16 }}>
              <option value="support">Support</option>
              <option value="manager">Manager</option>
              <option value="analyst">Analyst</option>
            </select>

            <label style={{ display: 'block', marginBottom: 8 }}>Upload complaint JSON</label>
            <input type="file" accept=".json" onChange={handleUpload} style={{ marginBottom: 12 }} />
            {uploadMessage && <p style={{ fontSize: 13, color: '#93c5fd' }}>{uploadMessage}</p>}

            <div style={{ marginTop: 18, padding: 12, background: '#111827', borderRadius: 10 }}>
              <strong>Tips</strong>
              <ul style={{ paddingLeft: 18, color: '#cbd5e1' }}>
                <li>Ask about billing, refunds, subscription cancellations, and delayed delivery.</li>
                <li>Upload your own complaint JSON to expand the knowledge base.</li>
              </ul>
            </div>
          </aside>

          <main style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid #334155', borderRadius: 16, padding: 16, display: 'flex', flexDirection: 'column', minHeight: 640 }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
              {messages.map((msg, index) => (
                <div key={index} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                  <div style={{ padding: '12px 14px', borderRadius: 14, background: msg.role === 'user' ? '#2563eb' : '#1f2937', whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && <div style={{ color: '#cbd5e1' }}>Thinking...</div>}
            </div>

            {sources.length > 0 && (
              <div style={{ marginBottom: 12, padding: 12, background: '#111827', borderRadius: 10 }}>
                <strong>Sources</strong>
                <ul style={{ margin: '8px 0 0 0', paddingLeft: 18 }}>
                  {sources.map((source) => <li key={source}>{source}</li>)}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10 }}>
              <textarea
                rows={3}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about complaints or desired resolution..."
                style={{ flex: 1, padding: 12, borderRadius: 10, border: '1px solid #475569' }}
              />
              <button onClick={askQuestion} disabled={loading} style={{ padding: '12px 16px', borderRadius: 10, background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer' }}>
                {loading ? 'Working...' : 'Ask'}
              </button>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;
