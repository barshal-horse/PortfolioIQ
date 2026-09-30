'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api, streamCopilotMessage, getAccessToken } from '@/lib/api';
import {
  Sparkles,
  X,
  Send,
  Loader2,
  Plus,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Wrench,
  KeyRound,
  CheckCircle2,
} from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: any[];
  tool_calls?: any[];
  streaming?: boolean;
}

interface CopilotSession {
  id: string;
  title: string;
  message_count: number;
}

interface CopilotSidebarProps {
  portfolioId: string;
  onClose: () => void;
}

export default function CopilotSidebar({ portfolioId, onClose }: CopilotSidebarProps) {
  const [sessions, setSessions] = useState<CopilotSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSessions, setShowSessions] = useState(false);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [geminiSource, setGeminiSource] = useState<'user' | 'server' | 'none' | null>(null);
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [keyInput, setKeyInput] = useState('');
  const [keySaving, setKeySaving] = useState(false);
  const [keyMsg, setKeyMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadGeminiStatus = useCallback(async () => {
    try {
      const st = await api.settings.getGeminiStatus();
      setGeminiSource(st?.source ?? 'none');
    } catch {
      setGeminiSource(null);
    }
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load sessions + Gemini key status on mount
  useEffect(() => {
    loadSessions();
    loadGeminiStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSessions = async () => {
    try {
      const list = await api.copilot.listSessions();
      setSessions(list || []);
    } catch (err: any) {
      // Session list requires backend; fail silently but show error state on send
      console.warn('Copilot sessions unavailable:', err?.message);
    }
  };

  const handleNewSession = async () => {
    setError(null);
    try {
      const session = await api.copilot.createSession(portfolioId);
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      inputRef.current?.focus();
    } catch (err: any) {
      setError(err?.message || 'Failed to create session');
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setShowSessions(false);
    setError(null);
    try {
      const data = await api.copilot.getMessages(sessionId, 50);
      const history: ChatMessage[] = (data?.messages || []).map((m: any) => ({
        id: m.id,
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content,
        citations: m.citations || [],
        tool_calls: m.tool_calls || [],
      }));
      setMessages(history);
    } catch (err: any) {
      setError(err?.message || 'Failed to load messages');
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.copilot.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to delete session');
    }
  };

  const handleSend = async () => {
    const content = input.trim();
    if (!content || sending) return;

    let sessionId: string | null = activeSessionId;
    if (!sessionId) {
      try {
        const session = await api.copilot.createSession(portfolioId);
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        sessionId = session.id;
      } catch (err: any) {
        setError(err?.message || 'Failed to create session — is the backend running?');
        return;
      }
    }
    if (!sessionId) return;

    setError(null);
    setSending(true);
    setInput('');

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
    };
    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    let streamError: string | null = null;
    const cancelStream = streamCopilotMessage(sessionId, content, {
      onToken: (chunk) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? { ...m, content: m.content + chunk } : m))
        );
      },
      onCitation: (citation) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, citations: [...(m.citations || []), citation] }
              : m
          )
        );
      },
      onDone: () => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? { ...m, streaming: false } : m))
        );
        setSending(false);
        loadSessions();
      },
      onNeedsKey: () => {
        setGeminiSource('none');
        setShowKeyForm(true);
      },
      onError: (message) => {
        streamError = message;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  streaming: false,
                  content: m.content || `⚠️ ${message}`,
                }
              : m
          )
        );
        setSending(false);
      },
    });

    // If the stream produces nothing within a timeout, surface an error
    setTimeout(() => {
      setMessages((prev) => {
        const target = prev.find((m) => m.id === assistantMsgId);
        if (target && target.streaming && !target.content) {
          setSending(false);
          return prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, streaming: false, content: '⚠️ No response received. Is GEMINI_API_KEY configured on the backend?' }
              : m
          );
        }
        return prev;
      });
    }, 30000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSaveKey = async () => {
    const key = keyInput.trim();
    if (!key || keySaving) return;
    setKeySaving(true);
    setKeyMsg(null);
    try {
      await api.settings.saveGeminiKey(key);
      setGeminiSource('user');
      setShowKeyForm(false);
      setKeyInput('');
      setKeyMsg({ ok: true, text: 'Gemini key connected — ask away!' });
      setError(null);
    } catch (err: any) {
      const detail = err?.message || 'Failed to save key';
      setKeyMsg({ ok: false, text: detail });
    } finally {
      setKeySaving(false);
    }
  };

  const handleRemoveKey = async () => {
    try {
      await api.settings.deleteGeminiKey();
      setGeminiSource('none');
      setKeyMsg({ ok: true, text: 'Gemini key removed.' });
    } catch (err: any) {
      setKeyMsg({ ok: false, text: err?.message || 'Failed to remove key' });
    }
  };

  const toggleToolExpansion = (msgId: string) => {
    setExpandedTools((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="w-96 bg-brand-card/95 border-l border-brand-border flex flex-col h-full z-20">
      {/* Header */}
      <div className="h-20 flex items-center justify-between px-5 border-b border-brand-border">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 bg-gradient-to-br from-brand-cyan/20 to-brand-violet/20 rounded-xl">
            <Sparkles className="h-5 w-5 text-brand-cyan" />
          </div>
          <div>
            <span className="text-base font-bold text-slate-100">AI Copilot</span>
            <p className="text-[10px] text-slate-500">Gemini-powered analysis</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-200 p-1.5 rounded-lg hover:bg-brand-card transition-colors cursor-pointer"
        >
          <X className="h-4.5 w-4.5" />
        </button>
      </div>

      {/* Session selector */}
      <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
        <button
          onClick={() => setShowSessions((s) => !s)}
          className="flex items-center space-x-2 text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          <span>{activeSessionId ? 'Current conversation' : 'New conversation'}</span>
          {showSessions ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
        <button
          onClick={handleNewSession}
          className="flex items-center space-x-1 text-xs text-brand-cyan hover:text-brand-cyan/80 font-semibold cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
          New
        </button>
      </div>

      {/* Sessions dropdown */}
      {showSessions && (
        <div className="max-h-48 overflow-y-auto border-b border-brand-border bg-brand-bg/40">
          {sessions.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-4">No previous conversations</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                onClick={() => handleSelectSession(s.id)}
                className={`flex items-center justify-between px-4 py-2.5 hover:bg-brand-card/60 cursor-pointer group ${
                  activeSessionId === s.id ? 'bg-brand-cyan/10 border-l-2 border-brand-cyan' : ''
                }`}
              >
                <span className="text-xs text-slate-300 truncate flex-1">{s.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-brand-red text-[10px] ml-2 transition-opacity cursor-pointer"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* Gemini key status / connect form */}
      <div className="px-4 py-2.5 border-b border-brand-border">
        {geminiSource === 'none' && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-[11px] text-amber-400">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>No Gemini key — copilot is offline</span>
            </div>
            <button
              onClick={() => { setShowKeyForm((s) => !s); setKeyMsg(null); }}
              className="flex items-center space-x-1 text-[11px] font-semibold text-brand-cyan hover:text-brand-cyan/80 cursor-pointer"
            >
              <KeyRound className="h-3 w-3" />
              Connect
            </button>
          </div>
        )}
        {geminiSource === 'user' && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-[11px] text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Gemini connected (your key)</span>
            </div>
            <button
              onClick={handleRemoveKey}
              className="text-[10px] text-slate-500 hover:text-brand-red cursor-pointer"
            >
              Remove
            </button>
          </div>
        )}
        {geminiSource === 'server' && (
          <div className="flex items-center space-x-1.5 text-[11px] text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Gemini connected (server key)</span>
          </div>
        )}
        {showKeyForm && (
          <div className="mt-2.5 space-y-2">
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveKey(); }}
              placeholder="Paste Gemini API key (AIza...)"
              className="w-full bg-brand-bg/60 border border-brand-border rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-brand-cyan"
              autoFocus
            />
            <div className="flex items-center justify-between">
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-slate-500 hover:text-slate-300 underline"
              >
                Get a free key →
              </a>
              <div className="space-x-2">
                <button
                  onClick={() => { setShowKeyForm(false); setKeyInput(''); setKeyMsg(null); }}
                  className="text-[11px] text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveKey}
                  disabled={!keyInput.trim() || keySaving}
                  className="px-2.5 py-1 text-[11px] font-semibold bg-gradient-to-br from-brand-cyan to-brand-violet text-slate-100 rounded-lg disabled:opacity-40 cursor-pointer"
                >
                  {keySaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
            {keyMsg && !keyMsg.ok && (
              <p className="text-[10px] text-brand-red">{keyMsg.text}</p>
            )}
          </div>
        )}
        {keyMsg?.ok && !showKeyForm && (
          <p className="text-[10px] text-emerald-400 mt-1">{keyMsg.text}</p>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Sparkles className="h-10 w-10 text-slate-700 mb-3" />
            <p className="text-sm text-slate-400 font-semibold mb-1">Ask about your portfolio</p>
            <p className="text-xs text-slate-600 max-w-[240px]">
              &quot;What&apos;s my portfolio risk?&quot; &quot;How did I do vs the S&amp;P 500?&quot; &quot;Should I rebalance?&quot;
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === 'user'
                    ? 'bg-brand-cyan/15 text-slate-100 border border-brand-cyan/20'
                    : 'bg-brand-bg/60 text-slate-200 border border-brand-border'
                }`}
              >
                <div className="whitespace-pre-wrap break-words leading-relaxed">
                  {msg.content || (msg.streaming ? 'Thinking…' : '')}
                  {msg.streaming && msg.content && (
                    <span className="inline-block w-1.5 h-3.5 bg-brand-cyan ml-0.5 animate-pulse align-middle" />
                  )}
                </div>

                {/* Tool calls expander */}
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <div className="mt-2">
                    <button
                      onClick={() => toggleToolExpansion(msg.id)}
                      className="flex items-center space-x-1 text-[10px] text-brand-violet hover:text-brand-violet/80 cursor-pointer"
                    >
                      <Wrench className="h-3 w-3" />
                      <span>{msg.tool_calls.length} tool calls</span>
                    </button>
                    {expandedTools[msg.id] && (
                      <div className="mt-1.5 space-y-1">
                        {msg.tool_calls.map((tc: any, idx: number) => (
                          <div
                            key={idx}
                            className="text-[10px] text-slate-500 bg-brand-bg/80 rounded px-2 py-1 font-mono"
                          >
                            {tc.name || tc.tool}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Citation chips */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {msg.citations.slice(0, 6).map((c: any, idx: number) => (
                      <span
                        key={idx}
                        className="text-[9px] px-1.5 py-0.5 bg-brand-violet/10 text-brand-violet border border-brand-violet/20 rounded-full"
                      >
                        {c.source || c.tool || 'data'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {error && (
          <div className="flex items-start space-x-2 p-3 bg-brand-red/10 border border-brand-red/25 rounded-xl text-brand-red text-xs">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-brand-border">
        <div className="flex items-end space-x-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your portfolio…"
            rows={2}
            disabled={sending}
            className="flex-1 bg-brand-bg/60 border border-brand-border rounded-xl px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-brand-cyan resize-none disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            className="p-2.5 bg-gradient-to-br from-brand-cyan to-brand-violet text-slate-100 rounded-xl hover:shadow-lg hover:shadow-brand-cyan/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            {sending ? (
              <Loader2 className="h-4.5 w-4.5 animate-spin" />
            ) : (
              <Send className="h-4.5 w-4.5" />
            )}
          </button>
        </div>
        <p className="text-[9px] text-slate-600 mt-2 text-center">
          Informational only — not financial advice.
        </p>
      </div>
    </div>
  );
}
