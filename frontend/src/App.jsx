import { useEffect, useRef, useState } from 'react'
import './App.css'

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
const ALLOWED_EXTENSIONS = ['.txt', '.pdf']
const API_BASE = 'http://localhost:8000'
const ACCESS_TOKEN_KEY = 'local_rag_access_token'
const REFRESH_TOKEN_KEY = 'local_rag_refresh_token'

function prettyFieldName(raw) {
  const map = {
    password: 'Password',
    email: 'Email',
    question: 'Question',
    refresh_token: 'Refresh token',
  }
  return map[raw] || raw
}

function formatFastApiDetail(detail) {
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const lines = detail
      .map((item) => {
        const msg = String(item?.msg || 'Invalid input.')
        const loc = Array.isArray(item?.loc) ? item.loc : []
        const field = loc.length > 0 ? loc[loc.length - 1] : ''
        const label = field ? prettyFieldName(String(field)) : ''
        return label ? `${label}: ${msg}` : msg
      })
      .filter(Boolean)
    if (lines.length > 0) {
      return lines.join(' ')
    }
  }

  return 'Request failed.'
}

async function readApiError(response, fallback = 'Request failed.') {
  try {
    const body = await response.json()
    return formatFastApiDetail(body?.detail) || fallback
  } catch {
    try {
      const text = (await response.text()).trim()
      return text || fallback
    } catch {
      return fallback
    }
  }
}

function formatDateTimeShort(value) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function normalizeConversationMessages(rows) {
  if (!Array.isArray(rows)) {
    return []
  }
  return rows
    .map((row) => {
      const role = row?.role === 'assistant' ? 'assistant' : 'user'
      const content = String(row?.content || '').trim()
      if (!content) {
        return null
      }
      return { role, content }
    })
    .filter(Boolean)
}

function normalizePreviewText(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
}

function App() {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [uploadedDocuments, setUploadedDocuments] = useState([])
  const [conversations, setConversations] = useState([])
  const [availableModels, setAvailableModels] = useState([])
  const [installedModels, setInstalledModels] = useState([])
  const [modelConfig, setModelConfig] = useState(null)
  const [conversationId, setConversationId] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false)
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [loadingConversationId, setLoadingConversationId] = useState('')
  const [deletingDocumentId, setDeletingDocumentId] = useState(null)
  const [installingModelName, setInstallingModelName] = useState('')
  const [selectingGenerationModelName, setSelectingGenerationModelName] = useState('')
  const [selectingRouterModelName, setSelectingRouterModelName] = useState('')
  const [modelView, setModelView] = useState('generation')
  const [modelSearch, setModelSearch] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [conversationSearch, setConversationSearch] = useState('')
  const [documentSearch, setDocumentSearch] = useState('')
  const [error, setError] = useState('')
  const [authError, setAuthError] = useState('')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [refreshToken, setRefreshToken] = useState('')
  const [currentUser, setCurrentUser] = useState(null)
  const [isAuthLoading, setIsAuthLoading] = useState(false)
  const [loadingDots, setLoadingDots] = useState('.')
  const fileInputRef = useRef(null)

  useEffect(() => {
    const storedAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY) || ''
    const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY) || ''
    if (!storedAccessToken) {
      return
    }

    setAccessToken(storedAccessToken)
    setRefreshToken(storedRefreshToken)

    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${storedAccessToken}`,
          },
        })
        if (!response.ok) {
          throw new Error('Stored session is invalid.')
        }
        const user = await response.json()
        setCurrentUser(user)
      } catch {
        clearSession()
      }
    })()
  }, [])

  useEffect(() => {
    if (!isLoading) {
      setLoadingDots('.')
      return
    }

    const values = ['.', '..', '...']
    let index = 0
    const timer = setInterval(() => {
      index = (index + 1) % values.length
      setLoadingDots(values[index])
    }, 350)

    return () => clearInterval(timer)
  }, [isLoading])

  function persistSession(tokens, user) {
    const nextAccessToken = (tokens?.access_token || '').trim()
    const nextRefreshToken = (tokens?.refresh_token || '').trim()

    setAccessToken(nextAccessToken)
    setRefreshToken(nextRefreshToken)
    setCurrentUser(user || null)

    if (nextAccessToken) {
      localStorage.setItem(ACCESS_TOKEN_KEY, nextAccessToken)
    } else {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
    }
    if (nextRefreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken)
    } else {
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
  }

  function clearSession() {
    setAccessToken('')
    setRefreshToken('')
    setCurrentUser(null)
    setConversationId('')
    setMessages([])
    setUploadedDocuments([])
    setConversations([])
    setAvailableModels([])
    setInstalledModels([])
    setModelConfig(null)
    setConversationSearch('')
    setDocumentSearch('')
    setModelSearch('')
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }

  async function refreshAccessToken(currentRefreshToken) {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: currentRefreshToken }),
      })
      if (!response.ok) {
        throw new Error(await readApiError(response, 'Session refresh failed.'))
      }
      const tokens = await response.json()
      persistSession(tokens, currentUser)
      return tokens.access_token
  }

  async function fetchWithAuth(path, init = {}, allowRetry = true) {
    if (!accessToken) {
      throw new Error('Please login first.')
    }

    const headers = new Headers(init.headers || {})
    headers.set('Authorization', `Bearer ${accessToken}`)

    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
    })

    if (response.status !== 401 || !allowRetry || !refreshToken) {
      return response
    }

    try {
      const nextAccessToken = await refreshAccessToken(refreshToken)
      headers.set('Authorization', `Bearer ${nextAccessToken}`)
      return await fetch(`${API_BASE}${path}`, {
        ...init,
        headers,
      })
    } catch {
      clearSession()
      return response
    }
  }

  async function loadDocuments({ showError = true } = {}) {
    if (!accessToken) {
      setUploadedDocuments([])
      return
    }
    try {
      setIsLoadingDocuments(true)
      const response = await fetchWithAuth('/documents?limit=100&offset=0')
      if (!response.ok) {
        throw new Error(await readApiError(response, `Failed to load documents (${response.status})`))
      }
      const data = await response.json()
      setUploadedDocuments(Array.isArray(data?.documents) ? data.documents : [])
    } catch (err) {
      if (showError) {
        setError(err instanceof Error ? err.message : 'Failed to load documents.')
      }
    } finally {
      setIsLoadingDocuments(false)
    }
  }

  async function loadConversations({ showError = true, search = '' } = {}) {
    if (!accessToken) {
      setConversations([])
      return
    }
    try {
      setIsLoadingConversations(true)
      const params = new URLSearchParams()
      params.set('limit', '50')
      params.set('offset', '0')
      const q = String(search || '').trim()
      if (q) {
        params.set('q', q)
        params.set('similarity_threshold', '0.2')
      }
      const response = await fetchWithAuth(`/conversations?${params.toString()}`)
      if (!response.ok) {
        throw new Error(await readApiError(response, `Failed to load conversations (${response.status})`))
      }
      const data = await response.json()
      setConversations(Array.isArray(data?.conversations) ? data.conversations : [])
    } catch (err) {
      if (showError) {
        setError(err instanceof Error ? err.message : 'Failed to load conversations.')
      }
    } finally {
      setIsLoadingConversations(false)
    }
  }

  async function loadModels({ showError = true, search = '' } = {}) {
    if (!accessToken) {
      setAvailableModels([])
      setInstalledModels([])
      setModelConfig(null)
      return
    }
    try {
      setIsLoadingModels(true)

      const params = new URLSearchParams()
      const q = String(search || '').trim()
      if (q) {
        params.set('q', q)
        params.set('similarity_threshold', '0.2')
      }
      const availablePath = params.toString() ? `/models/available?${params.toString()}` : '/models/available'

      const [availableResponse, installedResponse, configResponse] = await Promise.all([
        fetchWithAuth(availablePath),
        fetchWithAuth('/models/installed'),
        fetchWithAuth('/models/config'),
      ])

      if (!availableResponse.ok) {
        throw new Error(await readApiError(availableResponse, `Failed to load available models (${availableResponse.status})`))
      }
      if (!installedResponse.ok) {
        throw new Error(await readApiError(installedResponse, `Failed to load installed models (${installedResponse.status})`))
      }
      if (!configResponse.ok) {
        throw new Error(await readApiError(configResponse, `Failed to load model config (${configResponse.status})`))
      }

      const [availableData, installedData, configData] = await Promise.all([
        availableResponse.json(),
        installedResponse.json(),
        configResponse.json(),
      ])

      const nextAvailable = Array.isArray(availableData?.models) ? availableData.models : []
      const nextInstalled = Array.isArray(installedData?.models) ? installedData.models : []
      setAvailableModels(nextAvailable)
      setInstalledModels(nextInstalled)
      setModelConfig(configData || null)
    } catch (err) {
      if (showError) {
        setError(err instanceof Error ? err.message : 'Failed to load models.')
      }
    } finally {
      setIsLoadingModels(false)
    }
  }

  useEffect(() => {
    if (!currentUser || !accessToken) {
      return
    }
    void Promise.all([
      loadDocuments({ showError: false }),
      loadConversations({ showError: false, search: conversationSearch }),
      loadModels({ showError: false, search: modelSearch }),
    ])
  }, [currentUser, accessToken])

  useEffect(() => {
    if (!accessToken || !currentUser) {
      return
    }
    const handle = setTimeout(() => {
      void loadConversations({
        showError: false,
        search: conversationSearch,
      })
    }, 220)
    return () => clearTimeout(handle)
  }, [conversationSearch, accessToken, currentUser])

  useEffect(() => {
    if (!accessToken || !currentUser) {
      return
    }
    const handle = setTimeout(() => {
      void loadModels({
        showError: false,
        search: modelSearch,
      })
    }, 220)
    return () => clearTimeout(handle)
  }, [modelSearch, accessToken, currentUser])

  async function installModel(modelName) {
    const targetModel = String(modelName || '').trim()
    if (!targetModel || !accessToken) {
      return
    }

    try {
      setError('')
      setInstallingModelName(targetModel)
      const response = await fetchWithAuth('/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: targetModel }),
      })
      if (!response.ok) {
        throw new Error(await readApiError(response, `Model install failed (${response.status})`))
      }
      await response.json()
      await loadModels({ showError: false, search: modelSearch })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to install model.')
    } finally {
      setInstallingModelName('')
    }
  }

  async function selectGenerationModel(modelName) {
    const targetModel = String(modelName || '').trim()
    if (!targetModel || !accessToken) {
      return
    }
    try {
      setError('')
      setSelectingGenerationModelName(targetModel)
      const response = await fetchWithAuth('/models/generation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: targetModel }),
      })
      if (!response.ok) {
        throw new Error(await readApiError(response, `Generation model selection failed (${response.status})`))
      }
      const selectedConfig = await response.json()
      setModelConfig((prev) => ({
        ...(prev || {}),
        ...selectedConfig,
      }))
      await loadModels({ showError: false, search: modelSearch })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select generation model.')
    } finally {
      setSelectingGenerationModelName('')
    }
  }

  async function selectRouterModel(modelName) {
    const targetModel = String(modelName || '').trim()
    if (!targetModel || !accessToken) {
      return
    }
    try {
      setError('')
      setSelectingRouterModelName(targetModel)
      const response = await fetchWithAuth('/models/router', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: targetModel }),
      })
      if (!response.ok) {
        throw new Error(await readApiError(response, `Router model selection failed (${response.status})`))
      }
      const selectedConfig = await response.json()
      setModelConfig((prev) => ({
        ...(prev || {}),
        ...selectedConfig,
      }))
      await loadModels({ showError: false, search: modelSearch })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to select router model.')
    } finally {
      setSelectingRouterModelName('')
    }
  }

  async function openConversation(nextConversationId) {
    if (!nextConversationId || !accessToken) {
      return
    }
    try {
      setError('')
      setLoadingConversationId(nextConversationId)
      const response = await fetchWithAuth(
        `/conversations/${encodeURIComponent(nextConversationId)}/messages?limit=200`,
      )
      if (!response.ok) {
        throw new Error(await readApiError(response, `Failed to load messages (${response.status})`))
      }
      const data = await response.json()
      setMessages(normalizeConversationMessages(data?.messages))
      setConversationId(nextConversationId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation.')
    } finally {
      setLoadingConversationId('')
    }
  }

  async function deleteDocument(documentId) {
    if (!accessToken || !documentId) {
      return
    }
    const confirmed = window.confirm('Delete this document from your active index?')
    if (!confirmed) {
      return
    }
    try {
      setError('')
      setDeletingDocumentId(documentId)
      const response = await fetchWithAuth(`/documents/${documentId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(await readApiError(response, `Failed to delete document (${response.status})`))
      }
      await loadDocuments({ showError: false })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document.')
    } finally {
      setDeletingDocumentId(null)
    }
  }

  function startNewConversation() {
    setConversationId('')
    setMessages([])
    setError('')
  }

  async function submitAuth(action) {
    const email = authEmail.trim()
    const password = authPassword

    setAuthError('')
    setError('')
    if (!email || !password) {
      setAuthError('Email and password are required.')
      return
    }

    try {
      setIsAuthLoading(true)
      const response = await fetch(`${API_BASE}/auth/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        throw new Error(await readApiError(response, `Auth failed (${response.status})`))
      }

      const data = await response.json()
      persistSession(data.tokens, data.user)
      setConversationId('')
      setMessages([])
      setConversations([])
      setUploadedDocuments([])
      setConversationSearch('')
      setDocumentSearch('')
      setAuthPassword('')
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setIsAuthLoading(false)
    }
  }

  async function logout() {
    setAuthError('')
    try {
      if (refreshToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      }
    } finally {
      clearSession()
    }
  }

  function validateUploadFile(file) {
    const filename = (file?.name || '').toLowerCase()
    const isAllowedExt = ALLOWED_EXTENSIONS.some((ext) => filename.endsWith(ext))
    if (!isAllowedExt) {
      throw new Error('Only .txt and .pdf files are allowed.')
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      throw new Error('File is too large. Max size is 10 MB.')
    }
  }

  function onFileChange(event) {
    const files = Array.from(event.target.files || [])
    setSelectedFiles(files)
  }

  async function uploadDocument(event) {
    if (event) {
      event.preventDefault()
    }
    setError('')
    setAuthError('')

    if (!accessToken) {
      setError('Please login first.')
      return
    }

    if (selectedFiles.length === 0) {
      setError('Select file(s) first.')
      return
    }

    let successCount = 0
    let failedCount = 0

    try {
      setIsUploading(true)
      for (let i = 0; i < selectedFiles.length; i += 1) {
        const file = selectedFiles[i]
        try {
          validateUploadFile(file)

          const formData = new FormData()
          formData.append('file', file)

          const response = await fetchWithAuth('/documents', {
            method: 'POST',
            body: formData,
          })

          if (!response.ok) {
            throw new Error(await readApiError(response, `status ${response.status}`))
          }

          await response.json()
          successCount += 1
        } catch (err) {
          failedCount += 1
        }
      }

      if (failedCount > 0) {
        setError(`Upload finished: ${successCount} success, ${failedCount} failed.`)
      }
      setSelectedFiles([])
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      if (successCount > 0) {
        await loadDocuments({ showError: false })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setIsUploading(false)
    }
  }

  async function askQuestion(event) {
    event.preventDefault()
    setAuthError('')

    if (!accessToken) {
      setError('Please login first to chat.')
      return
    }

    const trimmed = question.trim()
    if (!trimmed) {
      setError('Please write a question first.')
      return
    }

    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setQuestion('')
    setIsLoading(true)
    setError('')

    try {
      const payload = {
        question: trimmed,
        debug: false,
      }
      if (conversationId) {
        payload.conversation_id = conversationId
      }

      const response = await fetchWithAuth('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(await readApiError(response, `Request failed with status ${response.status}`))
      }

      const data = await response.json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: (data.answer || 'No answer returned.').trim() },
      ])
      setConversationId(data.conversation_id || '')
      await loadConversations({ showError: false, search: conversationSearch })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }

  const conversationQuery = conversationSearch.trim().toLowerCase()
  const filteredConversations = conversations

  const documentQuery = documentSearch.trim().toLowerCase()
  const filteredDocuments = uploadedDocuments.filter((doc) => {
    if (!documentQuery) {
      return true
    }
    const filename = String(doc?.filename || '').toLowerCase()
    return filename.includes(documentQuery)
  })

  const installedModelNameSet = new Set(
    installedModels
      .map((item) => String(item?.name || '').trim())
      .filter(Boolean),
  )

  const sortedAvailableModels = [...availableModels].sort((a, b) => {
    const left = String(a?.name || '')
    const right = String(b?.name || '')
    const leftInstalled = installedModelNameSet.has(left)
    const rightInstalled = installedModelNameSet.has(right)
    if (leftInstalled !== rightInstalled) {
      return leftInstalled ? -1 : 1
    }
    return left.localeCompare(right, undefined, { sensitivity: 'base' })
  })

  const isAnswerView = modelView === 'generation'

  return (
    <main className="chat-page">
      <section className="auth-dock">
        <div className="auth-panel">
          {currentUser ? (
            <div className="auth-status">
              <span className="auth-user">Signed in as {currentUser.email}</span>
              <button type="button" className="logout-button" onClick={logout} disabled={isAuthLoading}>
                Logout
              </button>
            </div>
          ) : (
            <form
              className="auth-form"
              onSubmit={(event) => {
                event.preventDefault()
                void submitAuth('login')
              }}
            >
              <input
                type="email"
                placeholder="Email"
                value={authEmail}
                onChange={(event) => setAuthEmail(event.target.value)}
                disabled={isAuthLoading}
                autoComplete="email"
              />
              <input
                type="password"
                placeholder="Password"
                value={authPassword}
                onChange={(event) => setAuthPassword(event.target.value)}
                disabled={isAuthLoading}
                autoComplete="current-password"
              />
              <button type="submit" disabled={isAuthLoading}>
                {isAuthLoading ? 'Please wait...' : 'Login'}
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={isAuthLoading}
                onClick={() => void submitAuth('register')}
              >
                Register
              </button>
            </form>
          )}
          {authError ? <p className="auth-error">Auth error: {authError}</p> : null}
        </div>

        <aside className="side-panel">
          <div className="side-head">
            <h2 className="side-title">Chat History</h2>
            <button type="button" className="side-action-btn" onClick={startNewConversation} disabled={!accessToken}>
              New
            </button>
          </div>
          <input
            type="search"
            className="side-search"
            placeholder="Search history..."
            value={conversationSearch}
            onChange={(event) => setConversationSearch(event.target.value)}
            disabled={!accessToken}
          />
          {!accessToken ? (
            <p className="side-empty">Login to load history.</p>
          ) : filteredConversations.length === 0 ? (
            <p className="side-empty">
              {isLoadingConversations
                ? 'Searching conversations...'
                : conversationQuery
                  ? 'No matching conversations.'
                  : 'No conversations yet.'}
            </p>
          ) : (
            <>
              {isLoadingConversations ? (
                <p className="side-meta">Searching conversations...</p>
              ) : null}
              <ul className="side-list">
                {filteredConversations.map((item) => (
                  <li key={item.conversation_id} className="side-item">
                    <button
                      type="button"
                      className={`side-item-button ${
                        conversationId && conversationId === item.conversation_id ? 'side-item-button-active' : ''
                      }`}
                      onClick={() => void openConversation(item.conversation_id)}
                      disabled={loadingConversationId === item.conversation_id}
                    >
                      <span className="side-item-main">
                        {normalizePreviewText(item.last_message_preview) || 'Conversation'}
                      </span>
                      <span className="side-meta">
                        {item.message_count || 0} msg • {formatDateTimeShort(item.updated_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </section>

      <section className="chat-shell">
        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-text">Type a message to begin</p>
            </div>
          ) : null}

          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`message-row ${message.role === 'user' ? 'message-row-user' : 'message-row-assistant'}`}
            >
              <article className={`bubble ${message.role === 'user' ? 'bubble-user' : 'bubble-assistant'}`}>
                {message.content}
              </article>
            </div>
          ))}

          {isLoading ? (
            <div className="message-row message-row-assistant">
              <article className="bubble bubble-assistant">Thinking{loadingDots}</article>
            </div>
          ) : null}
        </div>

        <form onSubmit={askQuestion} className="composer">
          <textarea
            id="question-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            placeholder="Message Local RAG..."
            disabled={isLoading}
          />
          <div className="composer-actions">
            <div className="composer-upload">
              <label className="upload-picker" htmlFor="doc-upload">
                <input
                  ref={fileInputRef}
                  id="doc-upload"
                  type="file"
                  multiple
                  accept=".txt,.pdf,text/plain,application/pdf"
                  onChange={onFileChange}
                  disabled={isUploading}
                />
                <span className="upload-picker-label">
                  {selectedFiles.length > 0 ? `${selectedFiles.length} file(s) selected` : 'Choose .txt or .pdf'}
                </span>
              </label>
              <button
                type="button"
                className="upload-button"
                onClick={uploadDocument}
                disabled={isUploading || selectedFiles.length === 0 || !accessToken}
              >
                {isUploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
            <button type="submit" disabled={isLoading || isUploading}>
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>

        {error ? <p className="error-line">Error: {error}</p> : null}
      </section>

      <section className="right-dock">
        <aside className="side-panel">
          <h2 className="side-title">Uploaded Documents</h2>
          <input
            type="search"
            className="side-search"
            placeholder="Search documents..."
            value={documentSearch}
            onChange={(event) => setDocumentSearch(event.target.value)}
            disabled={!accessToken || isLoadingDocuments}
          />
          {!accessToken ? (
            <p className="side-empty">Login to see documents.</p>
          ) : isLoadingDocuments ? (
            <p className="side-empty">Loading documents...</p>
          ) : filteredDocuments.length === 0 ? (
            <p className="side-empty">
              {documentQuery ? 'No matching documents.' : 'No documents uploaded yet.'}
            </p>
          ) : (
            <ul className="side-list">
              {filteredDocuments.map((doc) => (
                <li key={`doc-${doc.id}`} className="side-item side-item-doc">
                  <div className="side-item-main-wrap">
                    <strong>{doc.filename}</strong>
                    <span className="side-meta">
                      Uploaded {formatDateTimeShort(doc.created_at)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="side-danger-btn"
                    onClick={() => void deleteDocument(doc.id)}
                    disabled={deletingDocumentId === doc.id}
                  >
                    {deletingDocumentId === doc.id ? 'Deleting...' : 'Delete'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <aside className="side-panel">
          <h2 className="side-title">LLM Models</h2>
          <div className="model-tabbar" role="tablist" aria-label="Model role selection">
            <div className="model-tab-item">
              <button
                type="button"
                role="tab"
                aria-selected={isAnswerView}
                className={`model-tab ${isAnswerView ? 'model-tab-active' : ''}`}
                onClick={() => setModelView('generation')}
              >
                Answer
              </button>
              <button
                type="button"
                className="model-info-btn"
                aria-label="About answer model"
                title="About answer model"
              >
                i
              </button>
              <div className="model-info-tip">
                The answer model writes the final response shown to the user. Larger models usually produce better
                quality but run slower. Smaller models are faster and lighter on local hardware.
              </div>
            </div>
            <div className="model-tab-item">
              <button
                type="button"
                role="tab"
                aria-selected={!isAnswerView}
                className={`model-tab ${!isAnswerView ? 'model-tab-active' : ''}`}
                onClick={() => setModelView('router')}
              >
                Router
              </button>
              <button
                type="button"
                className="model-info-btn"
                aria-label="About router model"
                title="About router model"
              >
                i
              </button>
              <div className="model-info-tip">
                The router model decides whether to handle a question as casual chat or run RAG retrieval. It can be a
                smaller fast model because it only returns a short routing decision.
              </div>
            </div>
          </div>
          <input
            type="search"
            className="side-search"
            placeholder="Search models..."
            value={modelSearch}
            onChange={(event) => setModelSearch(event.target.value)}
            disabled={!accessToken}
          />
          {!accessToken ? (
            <p className="side-empty">Login to view models.</p>
          ) : isLoadingModels ? (
            <p className="side-empty">Loading models...</p>
          ) : availableModels.length === 0 ? (
            <p className="side-empty">No models in allowlist.</p>
          ) : (
            <ul className="side-list side-list-models">
              {sortedAvailableModels.map((model) => {
                const modelName = String(model?.name || '').trim()
                const isInstalled = installedModelNameSet.has(modelName)
                const isInstalling = installingModelName === modelName
                const isGenerationActive = String(modelConfig?.generation_model || '') === modelName
                const isRouterActive = String(modelConfig?.router_model || '') === modelName
                const isSelectingGeneration = selectingGenerationModelName === modelName
                const isSelectingRouter = selectingRouterModelName === modelName
                const isActiveForCurrentView = isAnswerView ? isGenerationActive : isRouterActive
                return (
                  <li
                    key={`model-${model?.id || modelName}`}
                    className={`side-item side-item-doc ${isActiveForCurrentView ? 'side-item-model-active' : ''}`}
                  >
                    <div className="side-item-main-wrap">
                      <strong>{modelName}</strong>
                      <span className="side-meta">
                        {isActiveForCurrentView
                          ? (isAnswerView ? 'Answer active' : 'Router active')
                          : isInstalled
                            ? 'Installed'
                            : 'Not installed'}
                      </span>
                    </div>
                    {isInstalled ? (
                      <div className="side-action-group">
                        <button
                          type="button"
                          className="side-action-btn"
                          onClick={() => {
                            if (isAnswerView) {
                              void selectGenerationModel(modelName)
                            } else {
                              void selectRouterModel(modelName)
                            }
                          }}
                          disabled={
                            isActiveForCurrentView ||
                            (isAnswerView ? isSelectingGeneration : isSelectingRouter) ||
                            Boolean(installingModelName) ||
                            Boolean(selectingGenerationModelName) ||
                            Boolean(selectingRouterModelName)
                          }
                        >
                          {isActiveForCurrentView
                            ? (isAnswerView ? 'Answer Active' : 'Router Active')
                            : (isAnswerView
                              ? (isSelectingGeneration ? 'Selecting...' : 'Set Answer')
                              : (isSelectingRouter ? 'Selecting...' : 'Set Router'))}
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="side-action-btn"
                        onClick={() => void installModel(modelName)}
                        disabled={
                          isInstalling ||
                          Boolean(installingModelName) ||
                          Boolean(selectingGenerationModelName) ||
                          Boolean(selectingRouterModelName)
                        }
                      >
                        {isInstalling ? 'Installing...' : 'Install'}
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </aside>
      </section>
    </main>
  )
}

export default App
