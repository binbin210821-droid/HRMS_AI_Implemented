import {
  cancelUploadSession,
  completeUploadSession,
  createUploadSession,
} from '../../features/attachments/attachmentsApi.js'

export class DirectUploadError extends Error {
  constructor(message, { fallbackAllowed = false, sessionId = null } = {}) {
    super(message)
    this.name = 'DirectUploadError'
    this.fallbackAllowed = fallbackAllowed
    this.sessionId = sessionId
  }
}

export async function calculateSha256(file) {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export async function uploadFilesDirectly({ files, context, onProgress, idempotencyKeys = [] }) {
  const completedSessionIds = []
  try {
    for (const [index, file] of files.entries()) {
      onProgress?.({ index, total: files.length, fileName: file.name, state: 'preparing' })
      const checksum = await calculateSha256(file)
      let session
      try {
        session = await createUploadSession(
          {
            ...context,
            file_name: file.name,
            content_type: file.type,
            file_size: file.size,
            checksum,
          },
          idempotencyKeys[index]?.create,
        )
      } catch (error) {
        throw new DirectUploadError(error.message, {
          fallbackAllowed: !error.status || error.status >= 500,
        })
      }

      onProgress?.({ index, total: files.length, fileName: file.name, state: 'uploading' })
      try {
        const response = await fetch(session.upload_url, {
          method: 'PUT',
          headers: session.required_headers,
          body: file,
        })
        if (!response.ok) {
          throw new DirectUploadError(`Tải tệp thất bại: ${response.status}`, {
            fallbackAllowed: response.status >= 500,
            sessionId: session.id,
          })
        }
        await completeUploadSession(session.id, idempotencyKeys[index]?.complete)
      } catch (error) {
        if (error instanceof DirectUploadError) throw error
        throw new DirectUploadError(error.message || 'Không thể xác minh tệp tải lên', {
          fallbackAllowed: !error.status || error.status >= 500,
          sessionId: session.id,
        })
      }
      completedSessionIds.push(session.id)
      onProgress?.({ index, total: files.length, fileName: file.name, state: 'verified' })
    }
    return completedSessionIds
  } catch (error) {
    const sessionId = error.sessionId
    if (sessionId) {
      await cancelUploadSession(sessionId).catch(() => {})
    }
    for (const completedSessionId of completedSessionIds) {
      await cancelUploadSession(completedSessionId).catch(() => {})
    }
    throw error
  }
}
