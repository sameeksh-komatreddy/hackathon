type Props = {
  show: boolean
  title: string
  body: string
  onClose: () => void
}

export default function Toast({ show, title, body, onClose }: Props) {
  return (
    <div id="toast" className={show ? 'show' : undefined} role="status">
      <div className="t-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#A85448" strokeWidth="2"><path d="M12 9v4" /><path d="M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>
      </div>
      <div className="t-text"><b>{title}</b><span>{body}</span></div>
      <button className="t-close" onClick={onClose}>Close</button>
    </div>
  )
}
