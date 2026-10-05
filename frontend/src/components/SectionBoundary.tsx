import { Component, type ReactNode } from 'react'

interface Props {
  name: string
  children: ReactNode
}

// one broken section shows a short note instead of blanking the whole page
export default class SectionBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return <p className="text-sm text-muted">Couldn't display {this.props.name}.</p>
    }
    return this.props.children
  }
}
