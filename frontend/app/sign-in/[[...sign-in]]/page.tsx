import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#0a0a0f',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: '24px'
    }}>
      <div style={{
        fontFamily: 'sans-serif',
        fontSize: '28px',
        fontWeight: '800',
        color: '#fff',
        letterSpacing: '-0.5px'
      }}>
        🏋️ FitGenius
      </div>
      <SignIn />
    </div>
  )
}
