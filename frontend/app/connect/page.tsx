'use client'

import { useState } from 'react'
import axios from 'axios'

export default function ConnectPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleMockData = async () => {
    setIsLoading(true)
    setMessage('')
    
    try {
      const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/mock_tasks`)
      setMessage(`✅ ${response.data.message}. Created ${response.data.tasks_created} tasks.`)
    } catch (error) {
      setMessage('❌ Error seeding mock data. Please try again.')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGmailConnect = async () => {
    setIsLoading(true)
    setMessage('')
    
    try {
      // First, get the auth URL
      const authResponse = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/gmail/auth`)
      
      // For demo purposes, directly fetch mock emails
      const fetchResponse = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/gmail/fetch`)
      setMessage(`✅ ${fetchResponse.data.message}. Processed ${fetchResponse.data.emails_processed} emails.`)
    } catch (error) {
      setMessage('❌ Error connecting to Gmail. Please try again.')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async () => {
    if (!selectedFile) {
      setMessage('❌ Please select a file first.')
      return
    }

    setIsLoading(true)
    setMessage('')
    
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/upload/receipt`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )
      
      setMessage(`✅ Receipt uploaded successfully! Parsed: ${response.data.parsed_data.merchant} - ₹${response.data.parsed_data.amount}`)
      setSelectedFile(null)
    } catch (error) {
      setMessage('❌ Error uploading receipt. Please try again.')
      console.error('Error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    setSelectedFile(file || null)
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">
        Connect Your Data
      </h1>
      
      {message && (
        <div className={`p-4 rounded-lg mb-6 ${
          message.includes('✅') ? 'bg-success-50 text-success-800' : 'bg-danger-50 text-danger-800'
        }`}>
          {message}
        </div>
      )}
      
      <div className="space-y-6">
        {/* Mock Data Option */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Use Mock Data</h2>
              <p className="text-gray-600">Get started quickly with sample subscription data</p>
            </div>
          </div>
          <button
            onClick={handleMockData}
            disabled={isLoading}
            className="btn btn-primary"
          >
            {isLoading ? 'Loading...' : 'Use Mock Data'}
          </button>
        </div>

        {/* Gmail Connect Option */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Connect Gmail (Demo)</h2>
              <p className="text-gray-600">Connect your Gmail to automatically import tasks and receipts</p>
            </div>
          </div>
          <button
            onClick={handleGmailConnect}
            disabled={isLoading}
            className="btn btn-secondary"
          >
            {isLoading ? 'Connecting...' : 'Connect Gmail (Demo)'}
          </button>
        </div>

        {/* File Upload Option */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="w-10 h-10 bg-success-100 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-5 h-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Upload Receipt</h2>
              <p className="text-gray-600">Upload receipt files (text or .eml) to parse transaction data</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <input
              type="file"
              accept=".txt,.eml"
              onChange={handleFileChange}
              className="input"
            />
            
            {selectedFile && (
              <div className="text-sm text-gray-600">
                Selected: {selectedFile.name}
              </div>
            )}
            
            <button
              onClick={handleFileUpload}
              disabled={isLoading || !selectedFile}
              className="btn btn-success"
            >
              {isLoading ? 'Uploading...' : 'Upload Receipt'}
            </button>
          </div>
        </div>
      </div>
      
      <div className="mt-8 text-center">
        <a
          href="/dashboard"
          className="text-primary-600 hover:text-primary-700 font-medium"
        >
          Go to Dashboard →
        </a>
      </div>
    </div>
  )
}

