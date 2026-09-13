import Button from '../../components/ui/Button.jsx'

function AiSuggestionToggle({ isVisible, onToggle, className = '' }) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      className={className}
      aria-expanded={isVisible}
      onClick={onToggle}
    >
      {isVisible ? 'Ẩn gợi ý AI' : 'Hiện gợi ý AI'}
    </Button>
  )
}

export default AiSuggestionToggle
