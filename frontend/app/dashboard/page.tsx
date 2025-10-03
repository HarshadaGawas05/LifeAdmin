'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

interface Subscription {
  id: number
  merchant: string
  amount: number
  interval: string
  last_paid_date: string
  next_due_date: string
  confidence_score: number
  source: string
  is_active: boolean
}

interface DashboardData {
  total_monthly_spend: number
  subscriptions: Subscription[]
  count: number
}

export default function DashboardPage() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedSubscription, setSelectedSubscription] = useState<Subscription | null>(null)
  const [actionMessage, setActionMessage] = useState('')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/dashboard`)
      setDashboardData(response.data)
    } catch (error) {
      setError('Failed to load dashboard data')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAction = async (subscriptionId: number, action: string) => {
    try {
      let response
      switch (action) {
        case 'cancel':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/subscriptions/${subscriptionId}/cancel`)
          break
        case 'snooze':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/subscriptions/${subscriptionId}/snooze`)
          break
        case 'auto-pay':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/subscriptions/${subscriptionId}/auto-pay`)
          break
        default:
          return
      }
      
      setActionMessage(`✅ ${response.data.message}`)
      setTimeout(() => setActionMessage(''), 5000)
      
      // Refresh dashboard data
      fetchDashboardData()
    } catch (error) {
      setActionMessage('❌ Error performing action. Please try again.')
      console.error('Error:', error)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'text-success-600 bg-success-100'
    if (score >= 0.6) return 'text-warning-600 bg-warning-100'
    return 'text-danger-600 bg-danger-100'
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg text-gray-600">Loading dashboard...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center">
        <div className="text-danger-600 mb-4">{error}</div>
        <button onClick={fetchDashboardData} className="btn btn-primary">
          Retry
        </button>
      </div>
    )
  }

  if (!dashboardData || dashboardData.count === 0) {
    return (
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Dashboard</h1>
        <div className="text-gray-600 mb-8">
          No subscriptions found. <a href="/connect" className="text-primary-600 hover:text-primary-700">Connect your data</a> to get started.
        </div>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Dashboard</h1>
      
      {actionMessage && (
        <div className={`p-4 rounded-lg mb-6 ${
          actionMessage.includes('✅') ? 'bg-success-50 text-success-800' : 'bg-danger-50 text-danger-800'
        }`}>
          {actionMessage}
        </div>
      )}
      
      {/* Summary Card */}
      <div className="card p-6 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900">
              {formatCurrency(dashboardData.total_monthly_spend)}
            </h2>
            <p className="text-gray-600">Total Monthly Spend</p>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold text-gray-900">
              {dashboardData.count}
            </div>
            <p className="text-gray-600">Active Subscriptions</p>
          </div>
        </div>
      </div>

      {/* Subscriptions Table */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Recurring Subscriptions</h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merchant
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Paid
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Next Due
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {dashboardData.subscriptions.map((subscription) => (
                <tr key={subscription.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {subscription.merchant}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">
                      {formatCurrency(subscription.amount)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {subscription.interval}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(subscription.last_paid_date)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(subscription.next_due_date)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getConfidenceColor(subscription.confidence_score)}`}>
                      {Math.round(subscription.confidence_score * 100)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => setSelectedSubscription(subscription)}
                      className="text-xs text-primary-600 hover:text-primary-700 underline"
                    >
                      View Source
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button
                      onClick={() => handleAction(subscription.id, 'cancel')}
                      className="text-danger-600 hover:text-danger-900 text-xs"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleAction(subscription.id, 'snooze')}
                      className="text-warning-600 hover:text-warning-900 text-xs"
                    >
                      Snooze
                    </button>
                    <button
                      onClick={() => handleAction(subscription.id, 'auto-pay')}
                      className="text-success-600 hover:text-success-900 text-xs"
                    >
                      Auto-pay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Source Inspector Modal */}
      {selectedSubscription && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Source Information
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Merchant</label>
                  <p className="text-sm text-gray-900">{selectedSubscription.merchant}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Source Details</label>
                  <p className="text-sm text-gray-900">{selectedSubscription.source}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Confidence Score</label>
                  <p className="text-sm text-gray-900">{Math.round(selectedSubscription.confidence_score * 100)}%</p>
                </div>
              </div>
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setSelectedSubscription(null)}
                  className="btn btn-secondary"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

