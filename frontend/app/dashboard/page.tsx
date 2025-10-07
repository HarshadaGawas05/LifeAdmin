'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

interface Task {
  id: number
  name: string
  amount?: number
  category: string
  due_date?: string
  priority_score: number
  confidence_score: number
  source: string
  source_details?: any
  is_active: boolean
  is_recurring: boolean
  interval_days?: number
}

interface DashboardData {
  total_monthly_spend: number
  tasks: Task[]
  count: number
}

export default function DashboardPage() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [actionMessage, setActionMessage] = useState('')

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/tasks`)
      setDashboardData(response.data)
    } catch (error) {
      setError('Failed to load dashboard data')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAction = async (taskId: number, action: string) => {
    try {
      let response
      switch (action) {
        case 'cancel':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/tasks/${taskId}/cancel`)
          break
        case 'snooze':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/tasks/${taskId}/snooze`)
          break
        case 'auto-pay':
          response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/tasks/${taskId}/auto-pay`)
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

  const getPriorityColor = (score: number) => {
    if (score >= 0.8) return 'text-danger-600 bg-danger-100'
    if (score >= 0.6) return 'text-warning-600 bg-warning-100'
    return 'text-success-600 bg-success-100'
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'subscription': return 'text-blue-600 bg-blue-100'
      case 'bill': return 'text-orange-600 bg-orange-100'
      case 'assignment': return 'text-purple-600 bg-purple-100'
      case 'job_application': return 'text-green-600 bg-green-100'
      default: return 'text-gray-600 bg-gray-100'
    }
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
          No tasks found. <a href="/connect" className="text-primary-600 hover:text-primary-700">Connect your data</a> to get started.
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
            <p className="text-gray-600">Active Tasks</p>
          </div>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Tasks & Subscriptions</h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Due Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
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
              {dashboardData.tasks.map((task) => (
                <tr key={task.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {task.name}
                    </div>
                    {task.is_recurring && (
                      <div className="text-xs text-gray-500">
                        Recurring ({task.interval_days} days)
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getCategoryColor(task.category)}`}>
                      {task.category.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">
                      {task.amount ? formatCurrency(task.amount) : 'N/A'}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {task.due_date ? formatDate(task.due_date) : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getPriorityColor(task.priority_score)}`}>
                      {Math.round(task.priority_score * 100)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getConfidenceColor(task.confidence_score)}`}>
                      {Math.round(task.confidence_score * 100)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => setSelectedTask(task)}
                      className="text-xs text-primary-600 hover:text-primary-700 underline"
                    >
                      View Source
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button
                      onClick={() => handleAction(task.id, 'cancel')}
                      className="text-danger-600 hover:text-danger-900 text-xs"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleAction(task.id, 'snooze')}
                      className="text-warning-600 hover:text-warning-900 text-xs"
                    >
                      Snooze
                    </button>
                    {task.amount && (
                      <button
                        onClick={() => handleAction(task.id, 'auto-pay')}
                        className="text-success-600 hover:text-success-900 text-xs"
                      >
                        Auto-pay
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Source Inspector Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Source Information
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Task Name</label>
                  <p className="text-sm text-gray-900">{selectedTask.name}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Category</label>
                  <p className="text-sm text-gray-900">{selectedTask.category.replace('_', ' ')}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Source</label>
                  <p className="text-sm text-gray-900">{selectedTask.source}</p>
                </div>
                {selectedTask.source_details && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Source Details</label>
                    <div className="text-sm text-gray-900 bg-gray-50 p-2 rounded">
                      <pre className="whitespace-pre-wrap text-xs">
                        {JSON.stringify(selectedTask.source_details, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Confidence Score</label>
                  <p className="text-sm text-gray-900">{Math.round(selectedTask.confidence_score * 100)}%</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Priority Score</label>
                  <p className="text-sm text-gray-900">{Math.round(selectedTask.priority_score * 100)}%</p>
                </div>
              </div>
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setSelectedTask(null)}
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

