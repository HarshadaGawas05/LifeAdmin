'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

export default function AuthCallbackPage() {
  const router = useRouter()
  const params = useSearchParams()
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    const s = params.get('status')
    setStatus(s)
    const t = setTimeout(() => router.push('/dashboard'), 1000)
    return () => clearTimeout(t)
  }, [params, router])

  return (
    <div className="max-w-md mx-auto text-center py-20">
      <h1 className="text-2xl font-semibold mb-4">Authentication</h1>
      {status === 'success' ? (
        <p className="text-success-600">Connected! Redirecting…</p>
      ) : (
        <p className="text-danger-600">Failed to connect. Please try again.</p>
      )}
    </div>
  )
}


