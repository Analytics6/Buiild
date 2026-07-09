import { useEffect, useMemo, useState } from 'react';

const API_URL = 'http://localhost:8000';

function App() {
  const [view, setView] = useState('login');
  const [token, setToken] = useState(localStorage.getItem('complaint-token') || '');
  const [user, setUser] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: 'demo@support.ai', password: 'demo123' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState('support');
  const [chatId, setChatId] = useState(null);
  const [chats, setChats] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [uploadMessage, setUploadMessage] = useState('');

  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  useEffect(() => {
    const loadSession = async () => {
      if (!token) return;
      try {
        const res = await fetch(`${API_URL}/me`, { headers: authHeaders });
        if (res.ok) {
          const data = await res.json();
          setUser(data.user);
          setView('dashboard');
          loadChats();
        } else {
          localStorage.removeItem('complaint-token');
          setToken('');
        }
      } catch {
        localStorage.removeItem('complaint-token');
      }
    };
    loadSession();
  }, [token]);

  const loadChats = async () => {
    try {
      const res = await fetch(`${API_URL}/chats`, { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        setChats(data);
      }
    } catch {
      // ignore
    }
  };

  const loadTemplates = async () => {
    try {
      const res = await fetch(`${API_URL}/templates`);
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
      }
      localStorage.setItem('complaint-token', data.token);
      setToken(data.token);
      setUser(data.user);
      setView('dashboard');
      await loadChats();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const createConversation = async () => {
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ title: 'New case review' }),
      });
      const data = await res.json();
      if (res.ok) {
        setChatId(data.id);
        setMessages([]);
        setView('assistant');
        await loadChats();
      }
    } catch {
      setError('Unable to create a new conversation.');
    }
  };

  const openChat = async (id) => {
    setChatId(id);
    try {
      const res = await fetch(`${API_URL}/chat/${id}/messages`, { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.map((msg) => ({ role: msg.role, content: msg.content })));
      }
    } catch {
      setMessages([]);
    }
    setView('assistant');
  };

  const askQuestion = async () => {
    if (!question.trim() || !chatId) return;
    const userMessage = { role: 'user', content: question };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ question, template }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'The assistant could not answer');
      const assistantMessage = { role: 'assistant', content: data.answer || 'No answer returned' };
      setMessages([...nextMessages, assistantMessage]);
      await fetch(`${API_URL}/chat/${chatId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ role: 'user', content: question }),
      });
      await fetch(`${API_URL}/chat/${chatId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ role: 'assistant', content: assistantMessage.content }),
      });
    } catch (err) {
      setError(err.message);
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
      const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData, headers: authHeaders });
      const data = await res.json();
      setUploadMessage(`Uploaded ${file.name}: ${data.status}`);
    } catch {
      setUploadMessage('Upload failed.');
    }
  };

  const logout = () => {
    localStorage.removeItem('complaint-token');
    setToken('');
    setUser(null);
    setView('login');
  };

  return (
    <div style={{ minHeight: '100vh', background: '#07111f', color: '#f8fafc', fontFamily: 'Inter, Arial, sans-serif' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: 24 }}>
        {!user ? (
          <div style={{ maxWidth: 460, margin: '80px auto', padding: 28, borderRadius: 20, background: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155' }}>
            <h2 style={{ marginBottom: 8 }}>Customer Support Intelligence</h2>
            <p style={{ color: '#cbd5e1', marginBottom: 24 }}>Sign in to review complaints, respond with AI assistance, and manage your knowledge base.</p>
            <form onSubmit={handleLogin}>
              <label style={{ display: 'block', marginBottom: 8 }}>Email</label>
              <input value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} style={{ width: '100%', padding: 12, borderRadius: 10, marginBottom: 12 }} />
              <label style={{ display: 'block', marginBottom: 8 }}>Password</label>
              <input type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} style={{ width: '100%', padding: 12, borderRadius: 10, marginBottom: 16 }} />
              {error && <div style={{ color: '#fda4af', marginBottom: 12 }}>{error}</div>}
              <button type="submit" disabled={loading} style={{ width: '100%', padding: 12, borderRadius: 10, background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer' }}>
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>
        ) : (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <div>
                <h1 style={{ marginBottom: 6 }}>Support Operations Console</h1>
                <p style={{ margin: 0, color: '#cbd5e1' }}>Review complaint patterns, answer customer questions, and coordinate resolution workflows.</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 600 }}>{user.full_name}</div>
                <div style={{ color: '#cbd5e1', fontSize: 13 }}>{user.role}</div>
                <button onClick={logout} style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid #334155', background: '#111827', color: 'white', cursor: 'pointer' }}>Logout</button>
              </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20 }}>
              <aside style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155', borderRadius: 18, padding: 16, minHeight: 680 }}>
                <button onClick={() => setView('dashboard')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'dashboard' ? '#2563eb' : '#111827', border: '1px solid #334155', color: 'white', marginBottom: 10, cursor: 'pointer' }}>Dashboard</button>
                <button onClick={() => setView('assistant')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'assistant' ? '#2563eb' : '#111827', border: '1px solid #334155', color: 'white', marginBottom: 10, cursor: 'pointer' }}>Assistant</button>
                <button onClick={() => setView('knowledge')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'knowledge' ? '#2563eb' : '#111827', border: '1px solid #334155', color: 'white', marginBottom: 24, cursor: 'pointer' }}>Knowledge Base</button>

                <h4 style={{ marginBottom: 10 }}>Recent Conversations</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {chats.map((chat) => (
                    <button key={chat.id} onClick={() => openChat(chat.id)} style={{ textAlign: 'left', padding: 10, borderRadius: 10, background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', cursor: 'pointer' }}>
                      {chat.title}
                    </button>
                  ))}
                </div>
              </aside>

              <main style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid #334155', borderRadius: 18, padding: 20, minHeight: 680 }}>
                {view === 'dashboard' && (
                  <div>
                    <h3 style={{ marginTop: 0 }}>Operations Overview</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16, marginBottom: 24 }}>
                      <div style={{ padding: 16, borderRadius: 14, background: '#111827', border: '1px solid #334155' }}>
                        <div style={{ color: '#94a3b8' }}>Live Cases</div>
                        <div style={{ fontSize: 26, fontWeight: 700 }}>184</div>
                      </div>
                      <div style={{ padding: 16, borderRadius: 14, background: '#111827', border: '1px solid #334155' }}>
                        <div style={{ color: '#94a3b8' }}>Resolution SLA</div>
                        <div style={{ fontSize: 26, fontWeight: 700 }}>4.8h</div>
                      </div>
                      <div style={{ padding: 16, borderRadius: 14, background: '#111827', border: '1px solid #334155' }}>
                        <div style={{ color: '#94a3b8' }}>Escalations</div>
                        <div style={{ fontSize: 26, fontWeight: 700 }}>12%</div>
                      </div>
                    </div>
                    <button onClick={createConversation} style={{ padding: '12px 16px', borderRadius: 10, background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer' }}>Start new complaint review</button>
                  </div>
                )}

                {view === 'assistant' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <h3 style={{ margin: 0 }}>Complaint Assistant</h3>
                      <select value={template} onChange={(e) => setTemplate(e.target.value)} style={{ padding: 10, borderRadius: 10 }}>
                        {templates.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 12 }}>
                      {messages.length === 0 && <div style={{ color: '#cbd5e1' }}>Start a review with a question about billing, delivery, refunds, or product defects.</div>}
                      {messages.map((msg, index) => (
                        <div key={index} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                          <div style={{ padding: '12px 14px', borderRadius: 14, background: msg.role === 'user' ? '#2563eb' : '#1f2937', whiteSpace: 'pre-wrap' }}>
                            {msg.content}
                          </div>
                        </div>
                      ))}
                      {loading && <div style={{ color: '#cbd5e1' }}>Thinking...</div>}
                    </div>
                    {error && <div style={{ color: '#fda4af', marginBottom: 10 }}>{error}</div>}
                    <div style={{ display: 'flex', gap: 10 }}>
                      <textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Describe the complaint context and ask for a recommended action..." style={{ flex: 1, padding: 12, borderRadius: 10, border: '1px solid #475569' }} />
                      <button onClick={askQuestion} disabled={loading || !chatId} style={{ padding: '12px 16px', borderRadius: 10, background: '#2563eb', color: 'white', border: 'none', cursor: 'pointer' }}>
                        {loading ? 'Working...' : 'Ask'}
                      </button>
                    </div>
                  </div>
                )}

                {view === 'knowledge' && (
                  <div>
                    <h3 style={{ marginTop: 0 }}>Knowledge Base</h3>
                    <p style={{ color: '#cbd5e1' }}>Upload complaint JSON files to expand the retrieval corpus used by the assistant.</p>
                    <input type="file" accept=".json" onChange={handleUpload} style={{ marginBottom: 12 }} />
                    {uploadMessage && <p style={{ color: '#93c5fd' }}>{uploadMessage}</p>}
                  </div>
                )}
              </main>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
