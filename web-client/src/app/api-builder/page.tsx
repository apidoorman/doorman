'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import { SERVER_URL } from '@/utils/config'
import { postJson, fetchAllPaginated } from '@/utils/api'
import SearchableSelect from '@/components/SearchableSelect'

// Types for Schema
interface SchemaField {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  required: boolean
  min_length?: number
  max_length?: number
  min_value?: number
  max_value?: number
  pattern?: string
  enum?: string
  properties?: SchemaField[] // Nested fields
}

// Helper to convert array-based UI schema to backend dict schema
const convertToBackendSchema = (fields: SchemaField[]): Record<string, any> => {
  const schemaDict: Record<string, any> = {}
  fields.forEach(f => {
    const rules: any = { type: f.type, required: f.required }
    if (f.min_length !== undefined) rules.min_length = f.min_length
    if (f.max_length !== undefined) rules.max_length = f.max_length
    if (f.min_value !== undefined) rules.min_value = f.min_value
    if (f.max_value !== undefined) rules.max_value = f.max_value
    if (f.pattern) rules.pattern = f.pattern
    if (f.enum) rules.enum = f.enum.split(',').map(s => s.trim()).filter(Boolean)

    if (f.type === 'object' && f.properties && f.properties.length > 0) {
      rules.properties = convertToBackendSchema(f.properties)
    }

    schemaDict[f.name] = rules
  })
  return schemaDict
}

// Recursive Field List Component
const FieldEditor = ({
  fields,
  onChange,
  level = 0
}: {
  fields: SchemaField[],
  onChange: (fields: SchemaField[]) => void,
  level?: number
}) => {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  // New Field State
  const [newField, setNewField] = useState<SchemaField>({
    name: '', type: 'string', required: false
  })

  // Edit existing field state (simple implementation: remove and re-add or inline edit)
  // For simplicity keeping add/remove model, maybe inline later.

  const handleAddField = () => {
    if (!newField.name) return
    onChange([...fields, newField])
    setNewField({ name: '', type: 'string', required: false })
    setEditingIndex(null)
  }

  const handleRemoveField = (index: number) => {
    onChange(fields.filter((_, i) => i !== index))
  }

  const handleUpdateField = (index: number, updated: SchemaField) => {
    const newFields = [...fields]
    newFields[index] = updated
    onChange(newFields)
  }

  return (
    <div className={`space-y-4 ${level > 0 ? 'ml-4 border-l-2 border-gray-200 dark:border-gray-700 pl-4' : ''}`}>
      {/* Existing Fields */}
      {fields.map((f, i) => (
        <div key={i} className="group">
          <div className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 dark:hover:bg-white/5 border border-transparent hover:border-gray-200 dark:hover:border-gray-700">
            <span className="font-mono text-sm font-medium">{f.name}</span>
            <span className={`px-2 py-0.5 rounded text-xs ${f.type === 'string' ? 'bg-blue-100 text-blue-800' :
              f.type === 'number' ? 'bg-green-100 text-green-800' :
                f.type === 'object' ? 'bg-purple-100 text-purple-800' :
                  'bg-gray-100 text-gray-800'
              }`}>
              {f.type}
            </span>
            {f.required && <span className="text-xs text-error-600 font-medium">Req</span>}

            <div className="flex-1"></div>

            <button onClick={() => handleRemoveField(i)} className="opacity-0 group-hover:opacity-100 text-error-600 hover:text-error-800 text-xs px-2">Delete</button>
          </div>

          {/* Recursive Children for Object */}
          {f.type === 'object' && (
            <div className="mt-2 text-sm">
              <div className="text-gray-500 mb-2 text-xs uppercase tracking-wide font-semibold pl-2">Properties of {f.name}:</div>
              <FieldEditor
                fields={f.properties || []}
                onChange={(newProps) => handleUpdateField(i, { ...f, properties: newProps })}
                level={level + 1}
              />
            </div>
          )}
        </div>
      ))}

      {/* Add New Field Form */}
      {editingIndex === -1 ? (
        <div className="card p-3 bg-gray-50 dark:bg-gray-800/50 border border-dashed border-gray-300 dark:border-gray-700">
          <div className="flex gap-2 mb-2">
            <input
              placeholder="Field Name"
              className="input input-sm flex-1"
              value={newField.name}
              onChange={e => setNewField(p => ({ ...p, name: e.target.value }))}
              autoFocus
            />
            <select
              className="input input-sm w-32"
              value={newField.type}
              onChange={e => setNewField(p => ({ ...p, type: e.target.value as any }))}
            >
              <option value="string">String</option>
              <option value="number">Number</option>
              <option value="boolean">Boolean</option>
              <option value="array">Array</option>
              <option value="object">Object</option>
            </select>
          </div>

          <div className="flex items-center gap-4 mb-2">
            <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
              <input type="checkbox" checked={newField.required} onChange={e => setNewField(p => ({ ...p, required: e.target.checked }))} />
              Required
            </label>

            {/* Conditional Inputs */}
            {newField.type === 'string' && (
              <>
                <input placeholder="Min Len" type="number" className="input input-sm w-20" value={newField.min_length || ''} onChange={e => setNewField(p => ({ ...p, min_length: parseInt(e.target.value) || undefined }))} />
                <input placeholder="Max Len" type="number" className="input input-sm w-20" value={newField.max_length || ''} onChange={e => setNewField(p => ({ ...p, max_length: parseInt(e.target.value) || undefined }))} />
              </>
            )}
            {newField.type === 'number' && (
              <>
                <input placeholder="Min Val" type="number" className="input input-sm w-20" value={newField.min_value || ''} onChange={e => setNewField(p => ({ ...p, min_value: parseInt(e.target.value) || undefined }))} />
                <input placeholder="Max Val" type="number" className="input input-sm w-20" value={newField.max_value || ''} onChange={e => setNewField(p => ({ ...p, max_value: parseInt(e.target.value) || undefined }))} />
              </>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setEditingIndex(null)} className="btn btn-xs btn-ghost">Cancel</button>
            <button
              onClick={handleAddField}
              className="btn btn-xs btn-primary"
              disabled={!newField.name}
            >
              Add Field
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setEditingIndex(-1)}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-primary-600 transition-colors py-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          Add {level > 0 ? 'Nested ' : ''} Field
        </button>
      )}
    </div>
  )
}

const ApiBuilderPage = () => {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'settings' | 'schema'>('settings')

  // API Config State
  const [formData, setFormData] = useState({
    api_name: '',
    api_version: 'v1',
    api_type: 'REST',
    api_description: '',
    resource_name: '',
    collection_name: '',
    api_allowed_roles: [] as string[],
    api_allowed_groups: ['ALL'] as string[],
    active: true
  })

  // Schema State
  const [fields, setFields] = useState<SchemaField[]>([
    { name: 'name', type: 'string', required: true, min_length: 1 }
  ])

  // Helpers for multi-selects
  const [newRole, setNewRole] = useState('')
  const [newGroup, setNewGroup] = useState('')

  const fetchRoles = async (): Promise<string[]> => {
    const items = await fetchAllPaginated<any>(
      (p, s) => `${SERVER_URL}/platform/role/all?page=${p}&page_size=${s}`,
      (data) => (Array.isArray(data) ? data : (data.roles || data.response?.roles || [])),
      undefined,
      undefined,
      'cache:roles:all'
    )
    return items.map((r: any) => r.role_name || r.name || r).filter(Boolean)
  }

  const fetchGroups = async (): Promise<string[]> => {
    const items = await fetchAllPaginated<any>(
      (p, s) => `${SERVER_URL}/platform/group/all?page=${p}&page_size=${s}`,
      (data) => (Array.isArray(data) ? data : (data.groups || data.response?.groups || [])),
      undefined,
      undefined,
      'cache:groups:all'
    )
    return items.map((g: any) => g.group_name || g.name || g).filter(Boolean)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }))
  }

  const addRole = () => {
    const v = newRole.trim()
    if (!v) return
    if (formData.api_allowed_roles.includes(v)) return
    setFormData(prev => ({ ...prev, api_allowed_roles: [...prev.api_allowed_roles, v] }))
    setNewRole('')
  }
  const removeRole = (index: number) => setFormData(prev => ({ ...prev, api_allowed_roles: prev.api_allowed_roles.filter((_, i) => i !== index) }))

  const addGroup = () => {
    const v = newGroup.trim()
    if (!v) return
    if (formData.api_allowed_groups.includes(v)) return
    setFormData(prev => ({ ...prev, api_allowed_groups: [...prev.api_allowed_groups, v] }))
    setNewGroup('')
  }
  const removeGroup = (index: number) => setFormData(prev => ({ ...prev, api_allowed_groups: prev.api_allowed_groups.filter((_, i) => i !== index) }))

  const generateJsonPreview = (currentFields: SchemaField[]) => {
    const obj: any = {}
    currentFields.forEach(f => {
      if (f.type === 'string') obj[f.name] = "example"
      if (f.type === 'number') obj[f.name] = 123
      if (f.type === 'boolean') obj[f.name] = true
      if (f.type === 'array') obj[f.name] = []
      if (f.type === 'object') {
        obj[f.name] = f.properties ? JSON.parse(generateJsonPreview(f.properties)) : {}
      }
    })
    return JSON.stringify(obj, null, 2)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    if (!formData.resource_name) {
      setError('Resource Name is required.')
      setLoading(false)
      return
    }

    try {
      // Build Schema Dict Recursive
      const schemaDict = convertToBackendSchema(fields)

      const apiPayload = {
        api_name: formData.api_name,
        api_version: formData.api_version,
        api_description: formData.api_description,
        api_type: formData.api_type, // 'REST' | 'GRAPHQL'
        api_is_crud: true,
        api_crud_collection: formData.collection_name || undefined,
        api_crud_schema: schemaDict,
        api_allowed_roles: formData.api_allowed_roles.length > 0 ? formData.api_allowed_roles : undefined,
        api_allowed_groups: formData.api_allowed_groups.length > 0 ? formData.api_allowed_groups : ['ALL'],
        api_servers: [],
        active: formData.active,
        api_auth_required: true
      }

      await postJson(`${SERVER_URL}/platform/api`, apiPayload)

      const resource = formData.resource_name.startsWith('/') ? formData.resource_name : `/${formData.resource_name}`
      const resourceId = `${resource}/{id}`

      const endpoints = [
        { method: 'GET', uri: resource, desc: `List all ${formData.resource_name}` },
        { method: 'POST', uri: resource, desc: `Create new ${formData.resource_name}` },
        { method: 'GET', uri: resourceId, desc: `Get single ${formData.resource_name} by ID` },
        { method: 'PUT', uri: resourceId, desc: `Update ${formData.resource_name} by ID` },
        { method: 'DELETE', uri: resourceId, desc: `Delete ${formData.resource_name} by ID` }
      ]

      for (const ep of endpoints) {
        await postJson(`${SERVER_URL}/platform/endpoint`, {
          api_name: formData.api_name,
          api_version: formData.api_version,
          endpoint_method: ep.method,
          endpoint_uri: ep.uri,
          endpoint_description: ep.desc
        })
      }

      router.push('/apis')
    } catch (err: any) {
      console.error('Failed to create API:', err)
      setError(err.message || 'Failed to create API.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="flex h-[calc(100vh-100px)] gap-6">
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col space-y-6 overflow-hidden">
          <div className="flex items-center justify-between shrink-0">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">API Builder</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Design your API schema and endpoints</p>
            </div>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <> <div className="spinner mr-2"></div> Building... </>
              ) : 'Publish API'}
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-error-50 border border-error-200 p-4 text-error-700 dark:bg-error-900/20 dark:border-error-800 dark:text-error-300 shrink-0">
              {error}
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700 shrink-0">
            <button
              onClick={() => setActiveTab('settings')}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'settings'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
            >
              General Settings
            </button>
            <button
              onClick={() => setActiveTab('schema')}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'schema'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
            >
              Schema Definition
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto pr-2 pb-10">
            {activeTab === 'settings' ? (
              <div className="space-y-6 max-w-3xl">
                <div className="card p-6 space-y-4">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white">API Identity</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="label">API Name *</label>
                      <input name="api_name" className="input" placeholder="e.g. users-api" value={formData.api_name} onChange={handleChange} required />
                    </div>
                    <div>
                      <label className="label">Version *</label>
                      <input name="api_version" className="input" placeholder="v1" value={formData.api_version} onChange={handleChange} required />
                    </div>
                  </div>
                  <div>
                    <label className="label">Protocol</label>
                    <select name="api_type" className="input" value={formData.api_type} onChange={handleChange}>
                      <option value="REST">REST</option>
                      <option value="GRAPHQL">GraphQL</option>
                      <option value="SOAP">SOAP</option>
                      <option value="GRPC">gRPC</option>
                    </select>
                  </div>
                  <div>
                    <label className="label">Description</label>
                    <textarea name="api_description" className="input" rows={2} value={formData.api_description} onChange={handleChange} />
                  </div>
                </div>

                <div className="card p-6 space-y-4">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white">Resources</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="label">Resource Path *</label>
                      <div className="flex items-center">
                        <span className="mr-2 text-gray-500">/</span>
                        <input name="resource_name" className="input" placeholder="users" value={formData.resource_name} onChange={(e) => setFormData(p => ({ ...p, resource_name: e.target.value.replace(/^\/+/, '') }))} required />
                      </div>
                    </div>
                    <div>
                      <label className="label">Collection Name</label>
                      <input name="collection_name" className="input" placeholder="Auto-generated" value={formData.collection_name} onChange={handleChange} />
                    </div>
                  </div>
                </div>

                <div className="card p-6 space-y-4">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white">Access Control</h3>
                  <div>
                    <label className="label">Allowed Roles</label>
                    <SearchableSelect value={newRole} onChange={setNewRole} onAdd={addRole} onKeyPress={e => e.key === 'Enter' && addRole()} placeholder="Select role" fetchOptions={fetchRoles} addButtonText="Add" restrictToOptions />
                    <div className="flex flex-wrap gap-2 mt-2">
                      {formData.api_allowed_roles.map((r, i) => (
                        <span key={i} className="badge badge-primary flex items-center gap-1">{r} <button onClick={() => removeRole(i)} className="hover:text-white">×</button></span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="label">Allowed Groups</label>
                    <SearchableSelect value={newGroup} onChange={setNewGroup} onAdd={addGroup} onKeyPress={e => e.key === 'Enter' && addGroup()} placeholder="Select group" fetchOptions={fetchGroups} addButtonText="Add" restrictToOptions />
                    <div className="flex flex-wrap gap-2 mt-2">
                      {formData.api_allowed_groups.map((g, i) => (
                        <span key={i} className="badge badge-success flex items-center gap-1">{g} <button onClick={() => removeGroup(i)} className="hover:text-white">×</button></span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full gap-6">
                {/* Schema List */}
                <div className="flex-1 flex flex-col">
                  <div className="card flex-1 flex flex-col overflow-hidden">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                      <h3 className="font-medium">Data Model</h3>
                      <p className="text-xs text-gray-500 mt-1">Define your database schema with nested objects.</p>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4">
                      <FieldEditor fields={fields} onChange={setFields} />
                    </div>
                  </div>
                </div>

                {/* Preview / Helper */}
                <div className="w-80 shrink-0">
                  <div className="card p-4 sticky top-0">
                    <h3 className="font-medium mb-2 text-sm">JSON Preview</h3>
                    <pre className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-auto max-h-[400px]">
                      {generateJsonPreview(fields)}
                    </pre>
                    <p className="text-xs text-gray-500 mt-2">
                      This is how your data structure looks.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default ApiBuilderPage
