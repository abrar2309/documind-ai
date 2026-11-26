import { createElement, useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import "./agent.css";
import { api, clearTokens, getRefreshToken, getAccessToken, saveTokens, type User, type Workspace, type DocumentItem, type Citation, type ExactCountResult, type AgentResult } from "./lib/api";


function renderInlineMarkdown(text: string): ReactNode[] {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  return text.split(pattern).filter(Boolean).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return createElement("strong", { key: index }, part.slice(2, -2));
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return createElement("code", { key: index, className: "md-inline-code" }, part.slice(1, -1));
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return createElement("em", { key: index }, part.slice(1, -1));
    }
    return part;
  });
}

function renderMarkdown(markdown: string): ReactNode[] {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const output: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: string[] = [];
  let ordered = false;
  let code: string[] | null = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      output.push(createElement("p", { key: `p-${output.length}` },
        renderInlineMarkdown(paragraph.join(" "))));
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      const tag = ordered ? "ol" : "ul";
      output.push(createElement(tag, { key: `list-${output.length}` },
        ...list.map((item, i) => createElement("li", { key: i }, renderInlineMarkdown(item)))));
      list = [];
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph(); flushList();
      if (code === null) code = [];
      else {
        output.push(createElement("pre", { key: `code-${output.length}` },
          createElement("code", null, code.join("\n"))));
        code = null;
      }
      continue;
    }
    if (code !== null) { code.push(line); continue; }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    const number = line.match(/^\s*\d+[.)]\s+(.+)$/);
    const quote = line.match(/^\s*>\s?(.*)$/);

    if (heading) {
      flushParagraph(); flushList();
      const tag = `h${Math.min(heading[1].length + 1, 5)}`;
      output.push(createElement(tag, { key: `h-${output.length}` }, renderInlineMarkdown(heading[2])));
    } else if (bullet || number) {
      flushParagraph();
      const isOrdered = Boolean(number);
      if (list.length && ordered !== isOrdered) flushList();
      ordered = isOrdered;
      list.push((bullet || number)![1]);
    } else if (quote) {
      flushParagraph(); flushList();
      output.push(createElement("blockquote", { key: `q-${output.length}` }, renderInlineMarkdown(quote[1])));
    } else if (!line.trim()) {
      flushParagraph(); flushList();
    } else if (/^\s*([-*_])\s*\1\s*\1\s*$/.test(line)) {
      flushParagraph(); flushList();
      output.push(createElement("hr", { key: `hr-${output.length}` }));
    } else {
      flushList();
      paragraph.push(line.trim());
    }
  }
  flushParagraph(); flushList();
  if (code !== null) {
    output.push(createElement("pre", { key: `code-${output.length}` },
      createElement("code", null, code.join("\n"))));
  }
  return output;
}

type Mode = "login" | "register";
function App() {
  const [user,setUser]=useState<User|null>(null);
  const [workspaces,setWorkspaces]=useState<Workspace[]>([]);
  const [mode,setMode]=useState<Mode>("login");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [fullName,setFullName]=useState("");
  const [workspaceName,setWorkspaceName]=useState("");
  const [activeWorkspace,setActiveWorkspace]=useState<Workspace|null>(null);
  const [documents,setDocuments]=useState<DocumentItem[]>([]);
  const [selectedFile,setSelectedFile]=useState<File|null>(null);
  const [question,setQuestion]=useState("");
  const [answer,setAnswer]=useState("");
  const [citations,setCitations]=useState<Citation[]>([]);
  const [conversationId,setConversationId]=useState<string|undefined>();
  const [history,setHistory]=useState<{id:string;title:string;created_at:string}[]>([]);
  const [countTerm,setCountTerm]=useState("");
  const [countResult,setCountResult]=useState<ExactCountResult|null>(null);
  const [agentMode,setAgentMode]=useState(false);
  const [agentTask,setAgentTask]=useState("Review my uploaded project documents. Identify the five most important risks, explain why each risk matters, and cite the source documents and pages.");
  const [agentResult,setAgentResult]=useState<AgentResult|null>(null);
  const loadDashboard=useCallback(async()=>{const [me,spaces]=await Promise.all([api.me(),api.workspaces()]);setUser(me);setWorkspaces(spaces);},[]);
  const loadDocuments=useCallback(async(id:string)=>setDocuments(await api.documents(id)),[]);
  const loadHistory=useCallback(async(id:string)=>setHistory(await api.conversations(id)),[]);
  useEffect(()=>{let live=true;async function init(){if(!getAccessToken()&&!getRefreshToken()){setLoading(false);return;}try{await loadDashboard();}catch{clearTokens();if(live)setUser(null);}finally{if(live)setLoading(false);}}void init();return()=>{live=false;};},[loadDashboard]);
  async function authSubmit(e:FormEvent){e.preventDefault();setBusy(true);setError("");try{if(mode==="register")await api.register({email,password,full_name:fullName});const tokens=await api.login({email,password});saveTokens(tokens);await loadDashboard();setPassword("");}catch(x){setError(x instanceof Error?x.message:"Authentication failed");}finally{setBusy(false);}}
  async function createWorkspace(e:FormEvent){e.preventDefault();setBusy(true);setError("");try{await api.createWorkspace(workspaceName);setWorkspaceName("");await loadDashboard();setNotice("Workspace created.");}catch(x){setError(x instanceof Error?x.message:"Could not create workspace");}finally{setBusy(false);}}
  async function openWorkspace(space:Workspace){setActiveWorkspace(space);setAgentMode(false);setAgentResult(null);setAnswer("");setCitations([]);setConversationId(undefined);setCountResult(null);setError("");try{await Promise.all([loadDocuments(space.id),loadHistory(space.id)]);}catch(x){setError(x instanceof Error?x.message:"Could not load workspace");}}
  async function upload(e:FormEvent){e.preventDefault();if(!activeWorkspace||!selectedFile)return;setBusy(true);setError("");setNotice("");try{const doc=await api.uploadDocument(activeWorkspace.id,selectedFile);setSelectedFile(null);const el=document.getElementById("document-upload") as HTMLInputElement|null;if(el)el.value="";await loadDocuments(activeWorkspace.id);setNotice(doc.status==="ready"?`${doc.original_filename} is ready. ${doc.chunk_count} searchable sections created.`:`Upload saved but processing failed: ${doc.error_message||"Unknown error"}`);}catch(x){setError(x instanceof Error?x.message:"Upload failed");}finally{setBusy(false);}}
  async function ask(e:FormEvent){e.preventDefault();if(!activeWorkspace||!question.trim())return;setBusy(true);setError("");try{const result=await api.chat(activeWorkspace.id,question,conversationId);setConversationId(result.conversation_id);setAnswer(result.answer);setCitations(result.citations);setQuestion("");await loadHistory(activeWorkspace.id);}catch(x){setError(x instanceof Error?x.message:"Question failed");}finally{setBusy(false);}}
  async function runAgent(e:FormEvent){e.preventDefault();if(!activeWorkspace||!agentTask.trim())return;setBusy(true);setError("");setNotice("");setAgentResult(null);try{const result=await api.agent(activeWorkspace.id,agentTask.trim());setAgentResult(result);await loadHistory(activeWorkspace.id);}catch(x){setError(x instanceof Error?x.message:"Agent task failed");}finally{setBusy(false);}}
  async function openConversation(id:string){if(!activeWorkspace)return;setBusy(true);setError("");try{const items=await api.messages(activeWorkspace.id,id);const lastAssistant=[...items].reverse().find(item=>item.role==="assistant");setConversationId(id);setAnswer(lastAssistant?.content||"This conversation has no answer yet.");setCitations(lastAssistant?.citations||[]);}catch(x){setError(x instanceof Error?x.message:"Could not load conversation");}finally{setBusy(false);}}
  async function countTermInDocument(documentId:string){if(!activeWorkspace||!countTerm.trim()){setError("Enter a word or phrase first.");return;}setBusy(true);setError("");setCountResult(null);try{setCountResult(await api.exactCount(activeWorkspace.id,documentId,countTerm.trim()));}catch(x){setError(x instanceof Error?x.message:"Exact count failed");}finally{setBusy(false);}}
  async function reindexDocument(documentId:string){if(!activeWorkspace)return;setBusy(true);setError("");try{await api.reindexDocument(activeWorkspace.id,documentId);await loadDocuments(activeWorkspace.id);setNotice("Document re-indexed successfully.");}catch(x){setError(x instanceof Error?x.message:"Re-index failed");}finally{setBusy(false);}}
  async function deleteDocument(documentId:string){if(!activeWorkspace||!window.confirm("Delete this document and its indexed content?"))return;setBusy(true);setError("");try{await api.deleteDocument(activeWorkspace.id,documentId);await loadDocuments(activeWorkspace.id);setNotice("Document deleted.");}catch(x){setError(x instanceof Error?x.message:"Delete failed");}finally{setBusy(false);}}
  async function logout(){const refresh=getRefreshToken();try{if(refresh)await api.logout(refresh);}catch{}clearTokens();setUser(null);setWorkspaces([]);setActiveWorkspace(null);}
  function newChat(){setConversationId(undefined);setAnswer("");setCitations([]);setQuestion("");setError("");}
  if(loading)return <div className="loading-screen"><div className="loader"/>Loading DocuMind</div>;
  if(!user)return <main className="auth-layout"><section className="auth-visual"><div className="brand"><div className="brand-mark">D</div><span>DocuMind</span></div><div className="visual-copy"><div className="eyebrow">YOUR DOCUMENT WORKSPACE</div><h1>Knowledge,<br/>made searchable.</h1><p>Bring your documents together. Ask clear questions. Get answers linked to their original sources.</p><div className="visual-points"><span>Secure workspaces</span><span>PDF and text documents</span><span>AI answers with citations</span></div></div><div className="visual-footer">PRIVATE BY WORKSPACE · BUILT FOR RESEARCH</div></section><section className="auth-panel"><div className="auth-card"><div className="eyebrow">WELCOME TO DOCUMIND</div><h2>{mode==="login"?"Welcome back":"Create your account"}</h2><p className="muted">Sign in to continue to your knowledge workspace.</p><div className="auth-tabs"><button type="button" className={mode==="login"?"tab active":"tab"} aria-label="Choose sign-in mode" onClick={()=>setMode("login")}>Sign in</button><button type="button" className={mode==="register"?"tab active":"tab"} onClick={()=>setMode("register")}>Create account</button></div>{error&&<div className="alert error">{error}</div>}<form className="form-stack" onSubmit={authSubmit}>{mode==="register"&&<label>Full name<input value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Your name" required/></label>}<label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" required/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={mode==="register"?12:1} placeholder="Your password" required/></label><button className="primary-button" disabled={busy}>{busy?"Please wait…":mode==="login"?"Sign in":"Create account"}</button></form><p className="security-note">Your documents are kept inside your workspace.</p></div></section></main>;
  return <main className="dashboard"><aside className="sidebar"><div className="brand"><div className="brand-mark">D</div><span>DocuMind</span></div><div className="side-label">YOUR SPACE</div><button className={!activeWorkspace?"side-link selected":"side-link"} onClick={()=>setActiveWorkspace(null)}><span className="nav-glyph">⌂</span>Overview</button>{activeWorkspace&&<><button className={!agentMode?"side-link selected":"side-link"} onClick={()=>setAgentMode(false)}><span className="nav-glyph">▤</span>Documents & chat</button><button className={agentMode?"side-link selected":"side-link"} onClick={()=>{setAgentMode(true);setError("");}}><span className="nav-glyph">✦</span>AI Agent <span className="agent-nav-tag">NEW</span></button></>}<div className="sidebar-bottom"><div className="avatar">{(user.full_name||user.email).slice(0,1).toUpperCase()}</div><div className="user-mini"><strong>{user.full_name||"Account"}</strong><span>{user.email}</span></div><button className="icon-button" onClick={logout} title="Sign out">↗</button></div></aside><section className="dashboard-main"><header className="topbar"><div><span className="breadcrumb">Workspace</span><span className="breadcrumb-sep">/</span>{activeWorkspace?.name||"Overview"}</div><div className="top-user"><span className="status-dot"/>Signed in</div></header><div className="content">{error&&<div className="alert error">{error}</div>}{notice&&<div className="alert success">{notice}</div>}{!activeWorkspace?<><div className="welcome-row"><div><div className="eyebrow">YOUR KNOWLEDGE HUB</div><h1>Good to see you, {user.full_name?.split(" ")[0]||"there"}.</h1><p className="muted">Choose a workspace or create a new one to get started.</p></div><div className="welcome-symbol">✦</div></div><div className="stat-grid"><article className="stat-card"><span className="stat-icon purple">▦</span><span className="stat-label">WORKSPACES</span><strong>{workspaces.length}</strong><small>Your separate knowledge spaces</small></article><article className="stat-card"><span className="stat-icon green">▤</span><span className="stat-label">DOCUMENTS</span><strong>Open a workspace</strong><small>View your indexed files</small></article><article className="stat-card"><span className="stat-icon blue">✦</span><span className="stat-label">AI ASSISTANT</span><strong>Ready</strong><small>Answers grounded in sources</small></article></div><div className="section-heading"><div><h2>Your workspaces</h2><p className="muted">Open a space to browse documents and conversations.</p></div></div><div className="workspace-grid">{workspaces.map((w,i)=><button className="workspace-card workspace-open" key={w.id} onClick={()=>void openWorkspace(w)}><div className="workspace-card-top"><div className={`workspace-icon color-${i%3}`}>▦</div><span className="role-pill">Open workspace →</span></div><h3>{w.name}</h3><p>Private document library</p><div className="workspace-card-footer"><span>Documents and AI chat</span><span>→</span></div></button>)}<form className="create-card" onSubmit={createWorkspace}><div className="create-icon">＋</div><h3>Create a workspace</h3><p>Keep a project or subject in its own space.</p><input value={workspaceName} onChange={e=>setWorkspaceName(e.target.value)} placeholder="e.g. Research project" minLength={2} maxLength={150} required/><button className="primary-button" disabled={busy}>Create workspace</button></form></div></>:<><div className="welcome-row"><div><div className="eyebrow">WORKSPACE LIBRARY</div><h1>{activeWorkspace.name}</h1><p className="muted">Your files, searchable sections and document conversations.</p></div><button className="secondary-button" onClick={()=>setActiveWorkspace(null)}>← All workspaces</button></div><div className={agentMode?"stage2-grid agent-hidden":"stage2-grid"}><section className="panel library-panel"><div className="section-heading"><div><h2>Document library</h2><p className="muted">Upload a PDF or text file · Up to 20 MB</p></div><span className="count-badge">{documents.length} files</span></div><form className="upload-form" onSubmit={upload}><label className="file-picker" htmlFor="document-upload"><span className="upload-symbol">↑</span><span><strong>{selectedFile?selectedFile.name:"Choose a document"}</strong><small>PDF or TXT · Maximum 20 MB</small></span><span className="browse-label">Browse</span></label><input id="document-upload" className="visually-hidden" type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={e=>setSelectedFile(e.target.files?.[0]||null)} required/><button className="primary-button" disabled={busy||!selectedFile}>{busy?"Working…":"Upload and index"}</button></form><div className="document-list">{documents.map(doc=><article className="document-row" key={doc.id}><div className={`document-icon ${doc.content_type==="application/pdf"?"pdf":"txt"}`}>{doc.content_type==="application/pdf"?"PDF":"TXT"}</div><div className="document-info"><strong>{doc.original_filename}</strong><small>{(doc.file_size/1024).toFixed(1)} KB · {doc.chunk_count} sections · {doc.page_count?`${doc.page_count} pages`:"Text file"}</small>{doc.error_message&&<small className="error-text">{doc.error_message}</small>}</div><span className={`status-pill ${doc.status}`}>{doc.status==="ready"?"Ready":doc.status}</span><div className="document-actions">{doc.status==="ready"&&<button className="icon-button" title="Re-index document" onClick={()=>void reindexDocument(doc.id)}>↻</button>}<button className="icon-button danger" title="Delete document" onClick={()=>void deleteDocument(doc.id)}>×</button></div></article>)}{documents.length===0&&<div className="empty-state"><div className="empty-icon">▤</div><strong>Your library is empty</strong><p>Upload your first PDF or text file to begin.</p></div>}</div><div className="exact-count-panel"><div className="tool-heading"><div className="tool-icon">#</div><div><strong>Exact word and phrase count</strong><p className="muted">Search the complete extracted document, not just selected passages.</p></div></div><input value={countTerm} onChange={e=>setCountTerm(e.target.value)} placeholder="Enter a word or phrase, e.g. ball"/><div className="count-document-list">{documents.filter(doc=>doc.status==="ready").map(doc=><button type="button" className="secondary-button" key={doc.id} disabled={busy||!countTerm.trim()} onClick={()=>void countTermInDocument(doc.id)}>Count in {doc.original_filename}</button>)}</div>{countResult&&<div className="count-result"><strong>{countResult.count}</strong><span>matches for “{countResult.term}” in {countResult.filename}</span><small>Whole-word, case-insensitive · {countResult.page_count||"Text"} pages</small></div>}</div></section><section className="panel chat-panel"><div className="section-heading"><div><h2>Ask your documents</h2><p className="muted">Get answers with links back to source pages.</p></div><button type="button" className="text-button" onClick={newChat}>+ New chat</button></div><div className="conversation-history"><div className="history-heading"><strong>Recent conversations</strong><span>{history.length}</span></div>{history.length?history.map(item=><button type="button" className={conversationId===item.id?"history-item active":"history-item"} key={item.id} onClick={()=>void openConversation(item.id)}>{item.title}</button>):<p className="history-empty">Your conversations will appear here.</p>}</div><div className="chat-output">{answer?<><div className="answer-label">ANSWER</div><div className="answer-text">{answer}</div>{citations.length>0&&<div className="citations"><strong>Sources used</strong>{citations.map((c,i)=><article className="citation" key={c.chunk_id}><div><b>{i+1}. {c.filename}</b>{c.page_number&&<span> · Page {c.page_number}</span>}<span className="relevance">{Math.round(c.score*100)}% match</span></div><p>{c.excerpt}</p></article>)}</div>}</>:<div className="empty-chat"><div className="chat-orb">✦</div><strong>What would you like to know?</strong><p>Ask for a summary, find a detail, compare information or explore a topic in your documents.</p><div className="prompt-chips"><button type="button" onClick={()=>setQuestion("Summarize this document.")}>Summarize a document</button><button type="button" onClick={()=>setQuestion("What are the key points?")}>Find key points</button></div></div>}</div><form className="question-form" onSubmit={ask}><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask a question about your documents…" rows={3} required/><div className="composer-footer"><span>Answers are grounded in your workspace files.</span><button className="primary-button" disabled={busy||!question.trim()}>{busy?"Searching…":"Ask DocuMind →"}</button></div></form></section></div>{agentMode&&<section className="agent-workspace"><div className="agent-intro"><div><div className="eyebrow">STAGE 3 · BOUNDED AGENT</div><h2>Let DocuMind work through your documents.</h2><p className="muted">The agent can list workspace files, search relevant passages, and count terms in complete source documents. It is limited to three tool steps per task.</p></div><div className="agent-orb">✦</div></div><div className="agent-safety"><strong>Workspace-scoped tools only</strong><span>No shell access, arbitrary SQL, file deletion, or unrestricted tool execution.</span></div><form className="agent-task-form" onSubmit={runAgent}><label htmlFor="agent-task">What should the agent do?</label><textarea id="agent-task" value={agentTask} onChange={e=>setAgentTask(e.target.value)} rows={5} maxLength={8000} required placeholder="Describe a task for your documents…"/><div className="agent-form-footer"><span>{agentTask.length}/8000 characters · Uses your selected workspace</span><button className="primary-button" disabled={busy||!agentTask.trim()}>{busy?"Agent is working…":"Run agent →"}</button></div></form>{busy&&agentMode&&<div className="agent-running"><span className="agent-spinner"/>The agent is planning and executing its bounded tools. Local model responses can take a little while.</div>}{agentResult&&<div className="agent-result"><div className="agent-result-heading"><div><span className="answer-label">AGENT RESPONSE</span><h3>Task completed</h3></div><span className="agent-complete">✓ Completed</span></div><div className="answer-text agent-answer">{renderMarkdown(agentResult.answer)}</div><div className="agent-steps"><div className="history-heading"><strong>Tool execution trace</strong><span>{agentResult.steps.length}/{agentResult.max_steps} steps</span></div>{agentResult.steps.length?agentResult.steps.map(step=><article className="agent-step" key={step.step}><span className="agent-step-number">{step.step}</span><div><strong>{step.tool.replaceAll("_"," ")}</strong><small>Allowlisted tool · {step.status}</small></div><span className="agent-step-status">✓</span></article>):<p className="muted">No tool steps were returned.</p>}</div><p className="agent-footnote">The response is saved in conversation history. Check document names and page references against the source files.</p></div>}</section>}</>}</div></section></main>;
}
export default App;
