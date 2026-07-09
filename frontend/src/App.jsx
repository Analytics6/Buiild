import { useEffect, useMemo, useState } from 'react';
import { BarChart3, Bot, Database, LayoutDashboard, MessageSquareText, Settings, ShieldCheck, Sparkles, UploadCloud } from 'lucide-react';
import { AreaChart, Area, BarChart, Bar, CartesianGrid, Cell, Legend, PieChart, Pie, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const API_URL = '/api';

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

  const chartData = [
    { name: 'Billing', value: 42 },
    { name: 'Delivery', value: 31 },
    { name: 'Products', value: 19 },
    { name: 'Support', value: 28 },
  ];

  const trendData = [
    { month: 'Jan', open: 20, resolved: 16 },
    { month: 'Feb', open: 24, resolved: 21 },
    { month: 'Mar', open: 28, resolved: 24 },
    { month: 'Apr', open: 32, resolved: 29 },
    { month: 'May', open: 35, resolved: 33 },
    { month: 'Jun', open: 38, resolved: 35 },
  ];

  const pieData = [
    { name: 'Escalated', value: 18 },
    { name: 'Resolved', value: 61 },
    { name: 'Pending', value: 21 },
  ];

  const caseRows = [
    { id: 'C-1042', customer: 'Alicia Chen', topic: 'Billing mismatch', impact: 'High', status: 'Escalated' },
    { id: 'C-1038', customer: 'Marcus Reed', topic: 'Delivery delay', impact: 'Medium', status: 'In review' },
    { id: 'C-1019', customer: 'Tina Gomez', topic: 'Refund request', impact: 'High', status: 'Resolved' },
  ];

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
    <div style={{ minHeight: '100vh', background: '#f4f7fb', color: '#0f172a', fontFamily: 'Inter, Arial, sans-serif' }}>
      <div style={{ maxWidth: 1500, margin: '0 auto', padding: 24 }}>
        {!user ? (
          <div style={{ maxWidth: 480, margin: '80px auto', padding: 32, borderRadius: 24, background: 'white', border: '1px solid #e2e8f0', boxShadow: '0 18px 45px rgba(15, 23, 42, 0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <ShieldCheck size={24} color="#2563eb" />
              <h2 style={{ margin: 0 }}>Customer Support Intelligence</h2>
            </div>
            <p style={{ color: '#64748b', marginBottom: 24 }}>Secure sign-in for complaint triage, AI-assisted response drafting, and operations analytics.</p>
            <form onSubmit={handleLogin}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>Email</label>
              <input value={loginForm.email} onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })} style={{ width: '100%', padding: 12, borderRadius: 10, marginBottom: 12, border: '1px solid #cbd5e1', background: '#f8fafc' }} />
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>Password</label>
              <input type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} style={{ width: '100%', padding: 12, borderRadius: 10, marginBottom: 16, border: '1px solid #cbd5e1', background: '#f8fafc' }} />
              {error && <div style={{ color: '#dc2626', marginBottom: 12 }}>{error}</div>}
              <button type="submit" disabled={loading} style={{ width: '100%', padding: 12, borderRadius: 10, background: 'linear-gradient(90deg, #2563eb, #3b82f6)', color: 'white', border: 'none', cursor: 'pointer' }}>
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>
        ) : (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, background: 'white', padding: 20, borderRadius: 20, border: '1px solid #e2e8f0', boxShadow: '0 10px 28px rgba(15, 23, 42, 0.05)' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Sparkles size={20} color="#2563eb" />
                  <h1 style={{ margin: 0, fontSize: 24 }}>Support Operations Console</h1>
                </div>
                <p style={{ margin: 0, color: '#64748b' }}>Run complaint triage, AI-assisted resolution workflows, and executive reporting from one workspace.</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700 }}>{user.full_name}</div>
                <div style={{ color: '#64748b', fontSize: 13 }}>{user.role}</div>
                <button onClick={logout} style={{ marginTop: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', background: '#f8fafc', color: '#0f172a', cursor: 'pointer' }}>Logout</button>
              </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20 }}>
              <aside style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 20, padding: 16, minHeight: 760, boxShadow: '0 10px 28px rgba(15, 23, 42, 0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
                  <LayoutDashboard size={18} color="#2563eb" />
                  <h3 style={{ margin: 0 }}>Workspace</h3>
                </div>
                <button onClick={() => setView('dashboard')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'dashboard' ? '#eff6ff' : 'white', border: view === 'dashboard' ? '1px solid #93c5fd' : '1px solid #e2e8f0', color: '#0f172a', marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}> <LayoutDashboard size={16}/> Dashboard</button>
                <button onClick={() => setView('assistant')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'assistant' ? '#eff6ff' : 'white', border: view === 'assistant' ? '1px solid #93c5fd' : '1px solid #e2e8f0', color: '#0f172a', marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}> <Bot size={16}/> Assistant</button>
                <button onClick={() => setView('reports')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'reports' ? '#eff6ff' : 'white', border: view === 'reports' ? '1px solid #93c5fd' : '1px solid #e2e8f0', color: '#0f172a', marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}> <BarChart3 size={16}/> Reports</button>
                <button onClick={() => setView('knowledge')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'knowledge' ? '#eff6ff' : 'white', border: view === 'knowledge' ? '1px solid #93c5fd' : '1px solid #e2e8f0', color: '#0f172a', marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}> <Database size={16}/> Knowledge Base</button>
                <button onClick={() => setView('settings')} style={{ width: '100%', padding: 12, borderRadius: 10, background: view === 'settings' ? '#eff6ff' : 'white', border: view === 'settings' ? '1px solid #93c5fd' : '1px solid #e2e8f0', color: '#0f172a', marginBottom: 24, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}> <Settings size={16}/> Settings</button>

                <div style={{ marginBottom: 12, color: '#64748b', fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6 }}>Operations</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ padding: 10, borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0' }}>Escalation queue</div>
                  <div style={{ padding: 10, borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0' }}>Resolution playbooks</div>
                  <div style={{ padding: 10, borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0' }}>Audit logs</div>
                </div>

                <div style={{ marginTop: 24, marginBottom: 10, color: '#64748b', fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6 }}>Recent Conversations</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {chats.map((chat) => (
                    <button key={chat.id} onClick={() => openChat(chat.id)} style={{ textAlign: 'left', padding: 10, borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0', color: '#0f172a', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <MessageSquareText size={14} color="#64748b" /> {chat.title}
                    </button>
                  ))}
                </div>
              </aside>

              <main style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 20, padding: 20, minHeight: 760, boxShadow: '0 10px 28px rgba(15, 23, 42, 0.05)' }}>
                {view === 'dashboard' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                      <div>
                        <h3 style={{ margin: 0 }}>Executive Overview</h3>
                        <p style={{ margin: '4px 0 0 0', color: '#64748b' }}>A snapshot of complaint volume, resolution quality, and support operations.</p>
                      </div>
                      <button onClick={createConversation} style={{ padding: '10px 14px', borderRadius: 10, background: 'linear-gradient(90deg, #2563eb, #3b82f6)', color: 'white', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}><Sparkles size={16}/> New review</button>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16, marginBottom: 20 }}>
                      {[
                        { label: 'Open cases', value: '184', sub: '+8% vs last week' },
                        { label: 'Avg. resolution', value: '4.8h', sub: '11% faster' },
                        { label: 'Escalations', value: '12%', sub: 'Stable' },
                        { label: 'CSAT impact', value: '92%', sub: 'Improved' },
                      ].map((card) => (
                        <div key={card.label} style={{ padding: 16, borderRadius: 14, background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                          <div style={{ color: '#64748b', fontSize: 13 }}>{card.label}</div>
                          <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>{card.value}</div>
                          <div style={{ color: '#2563eb', fontSize: 12, marginTop: 4 }}>{card.sub}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 0.9fr', gap: 16, marginBottom: 16 }}>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>Case volume trend</div>
                        <ResponsiveContainer width="100%" height={220}>
                          <AreaChart data={trendData}>
                            <CartesianGrid stroke="#e2e8f0" />
                            <XAxis dataKey="month" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <Area type="monotone" dataKey="open" stackId="1" stroke="#2563eb" fill="#93c5fd" />
                            <Area type="monotone" dataKey="resolved" stackId="1" stroke="#16a34a" fill="#86efac" />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>Case status mix</div>
                        <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={80} fill="#2563eb">
                              {pieData.map((entry, index) => <Cell key={entry.name} fill={['#2563eb', '#16a34a', '#f59e0b'][index % 3]} />)}
                            </Pie>
                            <Tooltip />
                            <Legend />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                    <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                      <div style={{ fontWeight: 700, marginBottom: 10 }}>Top complaint drivers</div>
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={chartData}>
                          <CartesianGrid stroke="#e2e8f0" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="value" fill="#2563eb" radius={[8, 8, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {view === 'assistant' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div>
                        <h3 style={{ margin: 0 }}>AI Complaint Assistant</h3>
                        <p style={{ margin: '4px 0 0 0', color: '#64748b' }}>Use retrieval-augmented answers grounded in the complaint corpus.</p>
                      </div>
                      <select value={template} onChange={(e) => setTemplate(e.target.value)} style={{ padding: 10, borderRadius: 10, border: '1px solid #cbd5e1' }}>
                        {templates.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 12 }}>
                      {messages.length === 0 && <div style={{ color: '#64748b' }}>Start a review with a question about billing, delivery, refunds, or product defects.</div>}
                      {messages.map((msg, index) => (
                        <div key={index} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                          <div style={{ padding: '12px 14px', borderRadius: 14, background: msg.role === 'user' ? '#2563eb' : '#f8fafc', color: msg.role === 'user' ? 'white' : '#0f172a', border: msg.role === 'assistant' ? '1px solid #e2e8f0' : 'none', whiteSpace: 'pre-wrap' }}>
                            {msg.content}
                          </div>
                        </div>
                      ))}
                      {loading && <div style={{ color: '#64748b' }}>Thinking...</div>}
                    </div>
                    {error && <div style={{ color: '#dc2626', marginBottom: 10 }}>{error}</div>}
                    <div style={{ display: 'flex', gap: 10 }}>
                      <textarea rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Describe the complaint context and ask for a recommended action..." style={{ flex: 1, padding: 12, borderRadius: 10, border: '1px solid #cbd5e1', background: '#f8fafc' }} />
                      <button onClick={askQuestion} disabled={loading || !chatId} style={{ padding: '12px 16px', borderRadius: 10, background: 'linear-gradient(90deg, #2563eb, #3b82f6)', color: 'white', border: 'none', cursor: 'pointer' }}>
                        {loading ? 'Working...' : 'Ask'}
                      </button>
                    </div>
                  </div>
                )}

                {view === 'reports' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                      <div>
                        <h3 style={{ margin: 0 }}>Operational Reports</h3>
                        <p style={{ margin: '4px 0 0 0', color: '#64748b' }}>Monthly trends, case breakdowns, and support performance metrics.</p>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ padding: '10px 14px', borderRadius: 10, background: '#f8fafc', border: '1px solid #e2e8f0' }}>Last 30 days</div>
                        <button style={{ padding: '10px 14px', borderRadius: 10, border: '1px solid #e2e8f0', background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}><BarChart3 size={16} /> Export</button>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16, marginBottom: 20 }}>
                      {[
                        { label: 'Reported issues', value: '412', sub: '7% higher' },
                        { label: 'Support response', value: '2.8h', sub: 'On target' },
                        { label: 'Resolution rate', value: '89%', sub: 'Stable' },
                      ].map((card) => (
                        <div key={card.label} style={{ padding: 16, borderRadius: 14, background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                          <div style={{ color: '#64748b', fontSize: 13 }}>{card.label}</div>
                          <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6 }}>{card.value}</div>
                          <div style={{ color: '#2563eb', fontSize: 12, marginTop: 4 }}>{card.sub}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>Resolution timeline</div>
                        <ResponsiveContainer width="100%" height={220}>
                          <AreaChart data={trendData}>
                            <CartesianGrid stroke="#e2e8f0" />
                            <XAxis dataKey="month" />
                            <YAxis />
                            <Tooltip />
                            <Area type="monotone" dataKey="resolved" stroke="#16a34a" fill="#dcfce7" />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>Priority distribution</div>
                        <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={chartData}>
                            <CartesianGrid stroke="#e2e8f0" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Bar dataKey="value" fill="#3b82f6" radius={[8, 8, 0, 0]}>
                              {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={['#2563eb', '#3b82f6', '#60a5fa', '#93c5fd'][index % 4]} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                )}

                {view === 'settings' && (
                  <div>
                    <div style={{ marginBottom: 16 }}>
                      <h3 style={{ margin: 0 }}>Application Settings</h3>
                      <p style={{ margin: '4px 0 0 0', color: '#64748b' }}>Configure your workspace preferences and integration settings.</p>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>Profile</div>
                        <div style={{ color: '#64748b', marginBottom: 12 }}>Manage your account details and role settings.</div>
                        <div style={{ marginBottom: 8 }}><strong>Email:</strong> {user.email}</div>
                        <div style={{ marginBottom: 8 }}><strong>Full name:</strong> {user.full_name}</div>
                        <div><strong>Role:</strong> {user.role}</div>
                      </div>
                      <div style={{ padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#fff' }}>
                        <div style={{ fontWeight: 700, marginBottom: 10 }}>OpenAI Configuration</div>
                        <div style={{ color: '#64748b', marginBottom: 12 }}>The assistant uses the server-side OpenAI key for secure model generation.</div>
                        <div style={{ padding: 12, borderRadius: 12, background: '#f8fafc', border: '1px solid #e2e8f0' }}>Server-side env: <code>OPENAI_API_KEY</code></div>
                      </div>
                    </div>
                    <div style={{ marginTop: 20, padding: 16, borderRadius: 16, border: '1px solid #e2e8f0', background: '#f8fafc' }}>
                      <div style={{ fontWeight: 700, marginBottom: 10 }}>Application Health</div>
                      <div style={{ color: '#64748b' }}>Frontend and backend are connected through the /api proxy. Ensure the backend is running to send requests successfully.</div>
                    </div>
                  </div>
                )}

                {view === 'knowledge' && (
                  <div>
                    <h3 style={{ marginTop: 0 }}>Knowledge Base & Intake</h3>
                    <p style={{ color: '#64748b' }}>Upload complaint JSON files to expand the retrieval corpus used by the assistant and keep the case library current.</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 16, borderRadius: 14, border: '1px dashed #cbd5e1', background: '#f8fafc', marginBottom: 16 }}>
                      <UploadCloud size={18} color="#2563eb" />
                      <input type="file" accept=".json" onChange={handleUpload} />
                    </div>
                    {uploadMessage && <p style={{ color: '#2563eb' }}>{uploadMessage}</p>}
                    <div style={{ marginTop: 20, border: '1px solid #e2e8f0', borderRadius: 14, overflow: 'hidden' }}>
                      <div style={{ background: '#f8fafc', padding: 12, fontWeight: 700 }}>Priority cases</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: '#fff' }}>
                            <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e2e8f0' }}>Case ID</th>
                            <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e2e8f0' }}>Customer</th>
                            <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e2e8f0' }}>Topic</th>
                            <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e2e8f0' }}>Impact</th>
                            <th style={{ textAlign: 'left', padding: 10, borderBottom: '1px solid #e2e8f0' }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {caseRows.map((row) => (
                            <tr key={row.id}>
                              <td style={{ padding: 10, borderBottom: '1px solid #f1f5f9' }}>{row.id}</td>
                              <td style={{ padding: 10, borderBottom: '1px solid #f1f5f9' }}>{row.customer}</td>
                              <td style={{ padding: 10, borderBottom: '1px solid #f1f5f9' }}>{row.topic}</td>
                              <td style={{ padding: 10, borderBottom: '1px solid #f1f5f9' }}>{row.impact}</td>
                              <td style={{ padding: 10, borderBottom: '1px solid #f1f5f9' }}>{row.status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
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
