import { SignIn } from '@clerk/clerk-react'

export default function Login() {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Ziskin Field Systems
          </h1>
          <p className="text-gray-400">
            Professional surveillance platform
          </p>
        </div>

        <SignIn
          appearance={{
            elements: {
              rootBox: 'mx-auto',
              card: 'bg-white shadow-xl',
            },
          }}
          redirectUrl="/dashboard"
        />
      </div>
    </div>
  )
}
