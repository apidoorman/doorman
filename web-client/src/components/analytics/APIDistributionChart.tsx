'use client'

import React from 'react'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

interface APIData {
  api: string
  count: number
}

interface APIDistributionChartProps {
  data: APIData[]
  title?: string
  height?: number
}

// Color palette for pie slices
const COLORS = [
  '#3b82f6', // blue
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
  '#6366f1', // indigo
  '#14b8a6', // teal
]

export default function APIDistributionChart({
  data,
  title = 'API Usage Distribution',
  height = 300
}: APIDistributionChartProps) {
  // Transform data for pie chart
  const chartData = data.map(item => ({
    name: item.api,
    value: item.count
  }))

  // Calculate total for percentages
  const total = chartData.reduce((sum, item) => sum + item.value, 0)

  // Format value for display
  const formatValue = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    return value.toString()
  }

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0]
      const percentage = ((data.value / total) * 100).toFixed(1)
      
      return (
        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm font-medium text-gray-900 dark:text-white mb-1">
            {data.name}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            <span className="font-medium">Requests:</span> {formatValue(data.value)}
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            <span className="font-medium">Percentage:</span> {percentage}%
          </p>
        </div>
      )
    }
    return null
  }

  // Custom label
  const renderCustomLabel = (entry: any) => {
    const percentage = ((entry.value / total) * 100).toFixed(0)
    // Only show label if percentage is > 5%
    if (parseFloat(percentage) > 5) {
      return `${percentage}%`
    }
    return ''
  }

  return (
    <div className="w-full">
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {title}
        </h3>
      )}
      
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomLabel}
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Pie>
          
          <Tooltip content={<CustomTooltip />} />
          
          <Legend
            verticalAlign="bottom"
            height={36}
            wrapperStyle={{ fontSize: '12px' }}
            formatter={(value, entry: any) => {
              const percentage = ((entry.payload.value / total) * 100).toFixed(1)
              return `${value} (${percentage}%)`
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
