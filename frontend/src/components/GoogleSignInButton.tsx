import { useEffect, useRef } from 'react'
import { GOOGLE_CLIENT_ID } from '../lib/config'

const CLIENT_ID = GOOGLE_CLIENT_ID
const GSI_SRC = 'https://accounts.google.com/gsi/client'

interface GoogleId {
  initialize: (config: {
    client_id: string
    callback: (response: { credential: string }) => void
  }) => void
  renderButton: (
    parent: HTMLElement,
    options: { theme?: string; size?: string; width?: number; text?: string },
  ) => void
}

function getGoogleId(): GoogleId | undefined {
  return (window as unknown as { google?: { accounts: { id: GoogleId } } }).google?.accounts?.id
}

function loadGsi(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (getGoogleId()) {
      resolve()
      return
    }
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('gsi load failed')))
      return
    }
    const script = document.createElement('script')
    script.src = GSI_SRC
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('gsi load failed'))
    document.head.appendChild(script)
  })
}

interface Props {
  onCredential: (idToken: string) => void
}

export default function GoogleSignInButton({ onCredential }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!CLIENT_ID) return
    let cancelled = false
    loadGsi()
      .then(() => {
        const id = getGoogleId()
        if (cancelled || !ref.current || !id) return
        id.initialize({
          client_id: CLIENT_ID,
          callback: (response) => onCredential(response.credential),
        })
        id.renderButton(ref.current, { theme: 'outline', size: 'large', text: 'continue_with' })
      })
      .catch(() => {
        // network blocked or offline; the password form still works
      })
    return () => {
      cancelled = true
    }
  }, [onCredential])

  // without a configured client id there is nothing to render
  if (!CLIENT_ID) return null
  return <div ref={ref} className="flex justify-center" />
}
