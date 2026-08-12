/**
 * @brief 分析模板管理 Hook
 *
 * 支持商户保存常用分析问题为模板，快速复用。
 * 使用 localStorage 持久化存储。
 */

import { useCallback, useMemo, useState } from 'react'

const STORAGE_KEY = 'analysis_templates'

export interface AnalysisTemplate {
  id: string
  question: string
  label: string
  createdAt: number
}

function loadTemplates(): AnalysisTemplate[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveTemplates(templates: AnalysisTemplate[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
}

export function useAnalysisTemplates() {
  const [templates, setTemplates] = useState<AnalysisTemplate[]>(loadTemplates)

  const addTemplate = useCallback((question: string, label?: string) => {
    const trimmed = question.trim()
    if (!trimmed) return

    // 去重
    if (templates.some((t) => t.question === trimmed)) return

    const newTemplate: AnalysisTemplate = {
      id: Date.now().toString(36),
      question: trimmed,
      label: label || trimmed.slice(0, 18) + (trimmed.length > 18 ? '...' : ''),
      createdAt: Date.now(),
    }

    const updated = [newTemplate, ...templates].slice(0, 20) // 最多 20 个
    setTemplates(updated)
    saveTemplates(updated)
    return newTemplate
  }, [templates])

  const removeTemplate = useCallback((id: string) => {
    const updated = templates.filter((t) => t.id !== id)
    setTemplates(updated)
    saveTemplates(updated)
  }, [templates])

  const hasTemplate = useCallback((question: string) => {
    return templates.some((t) => t.question === question.trim())
  }, [templates])

  return { templates, addTemplate, removeTemplate, hasTemplate }
}
