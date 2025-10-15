'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

interface Email {
  id: number
  email_id: string
  subject: string
  sender: string
  sent_at: string
  snippet: string
  category: string
  priority: string
  summary: string
  llm_status: string
  llm_processed_at?: string
  llm_error?: string
}

interface Category {
  name: string
  count: number
}

export default function SmartInboxPage() {
  const [emails, setEmails] = useState<Email[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [selectedPriority, setSelectedPriority] = useState<string>('')
  const [isClassifying, setIsClassifying] = useState(false)
  const [classificationMessage, setClassificationMessage] = useState('')

  useEffect(() => {
    fetchEmails()
    fetchCategories()
  }, [selectedCategory, selectedPriority])

  const fetchEmails = async () => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams()
      if (selectedCategory) params.append('category', selectedCategory)
      if (selectedPriority) params.append('priority', selectedPriority)
      
      const response = await axios.get(
        `${process.env.NEXT_PUBLIC_API_URL}/emails?${params.toString()}`,
        { withCredentials: true }
      )
      setEmails(response.data)
    } catch (error) {
      setError('Failed to load emails')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchCategories = async () => {
    try {
      const response = await axios.get(
        `${process.env.NEXT_PUBLIC_API_URL}/emails/categories`,
        { withCredentials: true }
      )
      setCategories(response.data.categories)
    } catch (error) {
      console.error('Error fetching categories:', error)
    }
  }

  const handleClassifyPending = async () => {
    try {
      setIsClassifying(true)
      setClassificationMessage('Starting classification...')
      
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/emails/classify-pending`,
        { limit: 50 },
        { withCredentials: true }
      )
      
      setClassificationMessage('✅ Classification started successfully!')
      setTimeout(() => setClassificationMessage(''), 5000)
      
      // Refresh emails after a short delay
      setTimeout(() => {
        fetchEmails()
        fetchCategories()
      }, 2000)
      
    } catch (error) {
      setClassificationMessage('❌ Failed to start classification')
      console.error('Error:', error)
    } finally {
      setIsClassifying(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High': return 'text-red-600 bg-red-100 border-red-200'
      case 'Medium': return 'text-yellow-600 bg-yellow-100 border-yellow-200'
      case 'Low': return 'text-green-600 bg-green-100 border-green-200'
      default: return 'text-gray-600 bg-gray-100 border-gray-200'
    }
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'Job Application': return 'text-blue-600 bg-blue-100'
      case 'Subscription': return 'text-purple-600 bg-purple-100'
      case 'Renewal': return 'text-orange-600 bg-orange-100'
      case 'Bill': return 'text-red-600 bg-red-100'
      case 'Reminder': return 'text-yellow-600 bg-yellow-100'
      case 'Offer': return 'text-green-600 bg-green-100'
      case 'Spam': return 'text-gray-600 bg-gray-100'
      default: return 'text-indigo-600 bg-indigo-100'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'classified': return 'text-green-600 bg-green-100'
      case 'pending': return 'text-yellow-600 bg-yellow-100'
      case 'failed': return 'text-red-600 bg-red-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  // Group emails by category
  const groupedEmails = emails.reduce((acc, email) => {
    const category = email.category || 'Unclassified'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(email)
    return acc
  }, {} as Record<string, Email[]>)

  // Sort emails within each category by priority
  Object.keys(groupedEmails).forEach(category => {
    groupedEmails[category].sort((a, b) => {
      const priorityOrder = { 'High': 1, 'Medium': 2, 'Low': 3 }
      return (priorityOrder[a.priority as keyof typeof priorityOrder] || 4) - 
             (priorityOrder[b.priority as keyof typeof priorityOrder] || 4)
    })
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-lg text-gray-600">Loading Smart Inbox...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center">
        <div className="text-red-600 mb-4">{error}</div>
        <button onClick={fetchEmails} className="btn btn-primary">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Smart Inbox</h1>
          <p className="text-gray-600 mt-2">AI-powered email categorization and prioritization</p>
        </div>
        <div className="flex items-center space-x-4">
          <button
            onClick={handleClassifyPending}
            disabled={isClassifying}
            className="btn btn-primary"
          >
            {isClassifying ? 'Classifying...' : 'Classify Pending Emails'}
          </button>
          <button
            onClick={() => {
              setSelectedCategory('')
              setSelectedPriority('')
            }}
            className="btn btn-secondary"
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Classification Message */}
      {classificationMessage && (
        <div className={`p-4 rounded-lg mb-6 ${
          classificationMessage.includes('✅') ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {classificationMessage}
        </div>
      )}

      {/* Filters */}
      <div className="card p-6 mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Categories</option>
              {categories.map((category) => (
                <option key={category.name} value={category.name}>
                  {category.name} ({category.count})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Priority</label>
            <select
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Priorities</option>
              <option value="High">High Priority</option>
              <option value="Medium">Medium Priority</option>
              <option value="Low">Low Priority</option>
            </select>
          </div>
        </div>
      </div>

      {/* Categories Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {categories.map((category) => (
          <div key={category.name} className="card p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">{category.count}</div>
            <div className="text-sm text-gray-600">{category.name}</div>
          </div>
        ))}
      </div>

      {/* Emails by Category */}
      {Object.keys(groupedEmails).length === 0 ? (
        <div className="text-center py-12">
          <div className="text-gray-500 mb-4">No emails found</div>
          <p className="text-gray-600">
            {selectedCategory || selectedPriority 
              ? 'Try adjusting your filters or classify pending emails'
              : 'Connect your Gmail and sync emails to get started'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedEmails).map(([category, categoryEmails]) => (
            <div key={category} className="card overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {category} ({categoryEmails.length})
                  </h3>
                  <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getCategoryColor(category)}`}>
                    {category}
                  </span>
                </div>
              </div>
              
              <div className="divide-y divide-gray-200">
                {categoryEmails.map((email) => (
                  <div key={email.id} className="p-6 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3 mb-2">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getPriorityColor(email.priority)}`}>
                            {email.priority}
                          </span>
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(email.llm_status)}`}>
                            {email.llm_status}
                          </span>
                        </div>
                        
                        <h4 className="text-sm font-medium text-gray-900 mb-1">
                          {email.subject || 'No Subject'}
                        </h4>
                        
                        <p className="text-sm text-gray-600 mb-2">
                          From: {email.sender}
                        </p>
                        
                        {email.summary && (
                          <p className="text-sm text-gray-700 mb-2 bg-blue-50 p-2 rounded">
                            <span className="font-medium">AI Summary:</span> {email.summary}
                          </p>
                        )}
                        
                        <p className="text-sm text-gray-500 mb-2">
                          {email.snippet}
                        </p>
                        
                        <div className="text-xs text-gray-400">
                          {formatDate(email.sent_at)}
                          {email.llm_processed_at && (
                            <span className="ml-2">
                              • Classified: {formatDate(email.llm_processed_at)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
