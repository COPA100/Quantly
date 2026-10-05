import { errorMessage } from '../lib/api'
import { googleEnabled } from '../lib/config'
import { useGoogleLogin } from '../lib/use-google-login'
import GoogleSignInButton from './GoogleSignInButton'

export default function GoogleAuthSection() {
  const mutation = useGoogleLogin()

  // hidden entirely until a Google client id is configured
  if (!googleEnabled) return null

  return (
    <div className="mt-5">
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-hairline" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-canvas px-2 text-xs text-muted-soft">or</span>
        </div>
      </div>
      <GoogleSignInButton onCredential={(token) => mutation.mutate(token)} />
      {mutation.isError && (
        <p className="mt-2 text-center text-sm text-loss">{errorMessage(mutation.error)}</p>
      )}
    </div>
  )
}
