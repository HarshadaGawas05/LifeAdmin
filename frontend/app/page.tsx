import Link from 'next/link'

export default function Home() {
  return (
    <div className="text-center">
      <h1 className="text-4xl font-bold text-gray-900 mb-8">
        Welcome to LifeAdmin
      </h1>
      <p className="text-xl text-gray-600 mb-12">
        Take control of your recurring subscriptions and expenses
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
        <div className="card p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            Connect Your Data
          </h2>
          <p className="text-gray-600 mb-6">
            Connect Gmail, upload receipts, or use mock data to get started
          </p>
          <Link href="/connect" className="btn btn-primary">
            Get Started
          </Link>
        </div>
        
        <div className="card p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            View Dashboard
          </h2>
          <p className="text-gray-600 mb-6">
            See all your subscriptions and manage them in one place
          </p>
          <Link href="/dashboard" className="btn btn-secondary">
            View Dashboard
          </Link>
        </div>
      </div>
      
      <div className="mt-16">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Features
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          <div className="text-center">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Receipt Upload</h4>
            <p className="text-sm text-gray-600">Upload receipts and automatically parse transaction data</p>
          </div>
          
          <div className="text-center">
            <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Recurrence Detection</h4>
            <p className="text-sm text-gray-600">Automatically detect recurring subscriptions from your transactions</p>
          </div>
          
          <div className="text-center">
            <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-warning-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Spending Analytics</h4>
            <p className="text-sm text-gray-600">Track your monthly spending and subscription costs</p>
          </div>
        </div>
      </div>
    </div>
  )
}

