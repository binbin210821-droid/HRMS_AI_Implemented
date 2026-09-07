import { useState } from 'react'

export default function AttachmentLink({ attachment, getDownloadUrl, className = '' }) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleClick() {
    if (isLoading) return
    const popup = window.open('', '_blank', 'noopener,noreferrer')
    setIsLoading(true)
    setError('')
    try {
      const result = await getDownloadUrl(attachment)
      if (!result?.url) throw new Error('Không nhận được liên kết tải tài liệu.')
      if (popup) {
        popup.location.href = result.url
      } else {
        window.location.assign(result.url)
      }
    } catch (requestError) {
      popup?.close()
      setError(requestError.message || 'Không thể mở tài liệu.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <span className="inline-flex flex-col items-start">
      <button
        type="button"
        className={className || 'font-semibold text-brand-700 underline'}
        onClick={() => void handleClick()}
        disabled={isLoading}
        title={error || undefined}
      >
        {isLoading ? 'Đang mở...' : attachment.file_name}
      </button>
      {error && <span className="mt-1 text-xs text-red-600">{error}</span>}
    </span>
  )
}
