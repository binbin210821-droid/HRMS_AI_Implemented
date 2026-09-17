import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useSearchParams } from 'react-router-dom'

import Modal from '../components/Modal.jsx'
import { FadeIn } from '../components/animations/index.js'
import MainLayout from '../components/layout/MainLayout.jsx'
import { Button, Input, Select, Textarea } from '../components/ui/index.js'
import { REALTIME_COALESCE_DELAY_MS, useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'
import { invalidateResource } from '../services/requestCoordinator.js'
import {
  listAlerts,
  listDepartmentAlertSummaries,
  resolveAlert,
  scanAlerts,
} from '../features/alerts/alertsApi.js'
import AiAlertProposalCard from '../features/alerts/AiAlertProposalCard.jsx'
import {
  applyCoordination,
  issueDepartmentDirective,
  listDepartmentDirectives,
  listCoordinationSuggestions,
} from '../features/coordination/coordinationApi.js'
import ManagerAlertDirectiveAction from '../features/coordination/ManagerAlertDirectiveAction.jsx'
import { getDirectiveStatusLabel } from '../features/coordination/directiveLabels.js'
import {
  formatActiveTaskTitles,
  formatCandidateWorkload,
  getCandidateTransferLimit,
} from '../features/coordination/workloadLabels.js'
import { useAuthStore } from '../stores/authStore.js'
import { generateIdempotencyKey } from '../utils/idempotency.js'
import { useActionFeedback } from '../components/feedback/index.js'

const DIRECTIVE_ALERT_TYPES = new Set(['early_warning', 'overload'])

function AlertsPage() {
  const [searchParams] = useSearchParams()
  const focusedAlertId = searchParams.get('alert')
  const role = useAuthStore((state) => state.role)
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()
  const [alerts, setAlerts] = useState([])
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [resolutionNote, setResolutionNote] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [alertTypeFilter, setAlertTypeFilter] = useState(
    () => searchParams.get('alert_type') || 'all',
  )
  const [severityFilter, setSeverityFilter] = useState(() => searchParams.get('severity') || 'all')
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || 'all')
  const [searchTerm, setSearchTerm] = useState('')
  const [employeeIdFilter, setEmployeeIdFilter] = useState(
    () => searchParams.get('employee_id') || '',
  )
  const [departmentIdFilter, setDepartmentIdFilter] = useState(
    () => searchParams.get('department_id') || '',
  )
  const [coordinationSuggestions, setCoordinationSuggestions] = useState({})
  const [selectedCoordination, setSelectedCoordination] = useState(null)
  const [coordinationForm, setCoordinationForm] = useState({
    target_employee_id: '',
    tasks_to_transfer: '1',
    note: '',
  })
  const [departmentSummaries, setDepartmentSummaries] = useState([])
  const [departmentSummaryLoading, setDepartmentSummaryLoading] = useState(false)
  const [departmentDirectives, setDepartmentDirectives] = useState([])
  const [selectedDepartment, setSelectedDepartment] = useState(null)
  const [departmentDirectiveSaving, setDepartmentDirectiveSaving] = useState(false)
  const [departmentDirectiveError, setDepartmentDirectiveError] = useState('')
  const [departmentDirectiveForm, setDepartmentDirectiveForm] = useState({
    alert_type: 'all',
    severity: 'all',
    note: '',
  })
  const [highlightedAlertId, setHighlightedAlertId] = useState(null)
  const [resolvingIds, setResolvingIds] = useState(() => new Set())
  const [newAlertBanners, setNewAlertBanners] = useState([])
  const coordinationIdempotencyKeyRef = useRef(null)
  const departmentDirectiveIdempotencyKeyRef = useRef(null)
  const bannerItemsRef = useRef([])
  const bannerTimerRef = useRef(null)
  const scrollTimerRef = useRef(null)
  const lastBannerReceivedAtRef = useRef(0)
  const isBannerVisibleRef = useRef(false)

  useEffect(() => {
    setAlertTypeFilter(searchParams.get('alert_type') || 'all')
    setSeverityFilter(searchParams.get('severity') || 'all')
    setStatusFilter(searchParams.get('status') || 'all')
    setSearchTerm(searchParams.get('search') || '')
    setEmployeeIdFilter(searchParams.get('employee_id') || '')
    setDepartmentIdFilter(searchParams.get('department_id') || '')
  }, [searchParams])

  useEffect(() => {
    if (!highlightedAlertId) return undefined
    const timer = window.setTimeout(() => setHighlightedAlertId(null), 2500)
    return () => window.clearTimeout(timer)
  }, [highlightedAlertId])

  useEffect(
    () => () => {
      if (bannerTimerRef.current) window.clearTimeout(bannerTimerRef.current)
      if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current)
    },
    [],
  )

  useEffect(() => {
    if (!focusedAlertId || isLoading) return undefined
    let element = document.getElementById(`alert-card-${focusedAlertId}`)
    if (!element && role === 'leadership') {
      const summary = departmentSummaries.find((item) => item.alert_ids?.includes(focusedAlertId))
      if (summary)
        element = document.getElementById(`department-alert-card-${summary.department_id}`)
    }
    if (!element) return undefined
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedAlertId(focusedAlertId)
    return undefined
  }, [alerts.length, departmentSummaries, focusedAlertId, isLoading, role])

  const loadAlerts = useCallback(async () => {
    try {
      setError('')
      const data = await listAlerts(undefined, 'all')
      setAlerts(data || [])
    } catch {
      setError('Không thể tải danh sách cảnh báo.')
    } finally {
      setIsLoading(false)
    }
    if (role === 'leadership') {
      setDepartmentSummaryLoading(true)
      try {
        const summaries = await listDepartmentAlertSummaries()
        setDepartmentSummaries(summaries || [])
      } catch {
        setError('Không thể tải tổng hợp cảnh báo theo phòng ban.')
      } finally {
        setDepartmentSummaryLoading(false)
      }
    }
    if (role === 'manager') {
      try {
        const suggestions = await listCoordinationSuggestions()
        setCoordinationSuggestions(
          Object.fromEntries((suggestions || []).map((item) => [item.alert_id, item])),
        )
      } catch {
        // Không để lỗi gợi ý điều phối làm gián đoạn danh sách cảnh báo.
        setCoordinationSuggestions({})
      }
    } else {
      setCoordinationSuggestions({})
    }
  }, [role])

  useEffect(() => {
    loadAlerts()
  }, [loadAlerts])

  const loadDepartmentDirectives = useCallback(async () => {
    try {
      const data = await listDepartmentDirectives()
      setDepartmentDirectives(data || [])
    } catch {
      // Không để lỗi theo dõi chỉ thị làm gián đoạn danh sách cảnh báo.
    }
  }, [])

  useEffect(() => {
    if (role === 'leadership') void loadDepartmentDirectives()
  }, [loadDepartmentDirectives, role])

  async function handleScan() {
    setIsScanning(true)
    setError('')
    try {
      const created = await scanAlerts()
      if (created?.length) {
        await loadAlerts()
      }
    } catch {
      setError('Không thể quét cảnh báo lúc này.')
    } finally {
      setIsScanning(false)
    }
  }

  async function handleResolve(event) {
    event.preventDefault()
    if (!selectedAlert) return
    const confirmed = await confirmAction({
      title: 'Xác nhận ghi nhận xử lý cảnh báo',
      description: 'Hệ thống sẽ chuyển cảnh báo này sang trạng thái đã xử lý.',
      details: [
        `Cảnh báo: ${selectedAlert.title}`,
        `Nhân viên: ${selectedAlert.employee_name}`,
        `Ghi chú: ${resolutionNote.trim() || 'Không thêm ghi chú'}`,
      ],
      confirmLabel: 'Xác nhận xử lý',
    })
    if (!confirmed) return
    setIsSaving(true)
    setError('')
    try {
      const updated = await resolveAlert(selectedAlert.id, resolutionNote)
      applyResolvedAlert(updated)
      setSelectedAlert(null)
      setResolutionNote('')
      notifyActionSuccess({
        title: 'Đã ghi nhận xử lý cảnh báo',
        message: `Cảnh báo của ${updated.employee_name || selectedAlert.employee_name} đã được cập nhật thành công.`,
        details: [updated.title || selectedAlert.title],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể cập nhật cảnh báo.'
      setError(message)
      notifyActionError({ title: 'Chưa ghi nhận xử lý', message })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleQuickResolve(alert) {
    if (resolvingIds.has(alert.id)) return
    const confirmed = await confirmAction({
      title: 'Xác nhận đánh dấu đã xử lý',
      description: 'Bạn đang xác nhận cảnh báo đã được xử lý mà không thêm ghi chú.',
      details: [`Cảnh báo: ${alert.title}`, `Nhân viên: ${alert.employee_name}`],
      confirmLabel: 'Đánh dấu đã xử lý',
    })
    if (!confirmed) return
    setResolvingIds((current) => new Set(current).add(alert.id))
    setError('')
    try {
      const updated = await resolveAlert(alert.id, '')
      applyResolvedAlert(updated)
      notifyActionSuccess({
        title: 'Đã đánh dấu cảnh báo đã xử lý',
        message: `Cảnh báo của ${updated.employee_name || alert.employee_name} đã được cập nhật thành công.`,
        details: [updated.title || alert.title],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể cập nhật cảnh báo.'
      setError(message)
      notifyActionError({ title: 'Chưa cập nhật cảnh báo', message })
    } finally {
      setResolvingIds((current) => {
        const next = new Set(current)
        next.delete(alert.id)
        return next
      })
    }
  }

  function applyResolvedAlert(updated) {
    setAlerts((current) => current.map((alert) => (alert.id === updated.id ? updated : alert)))
    setHighlightedAlertId(updated.id)
  }

  async function handleApplyCoordination(alert, payload = {}) {
    const suggestion = coordinationSuggestions[alert.id]
    const candidate = suggestion?.candidates?.find(
      (item) => item.employee_id === payload.target_employee_id,
    )
    const confirmed = await confirmAction({
      title: 'Xác nhận áp dụng phương án điều phối',
      description: 'Hệ thống sẽ chuyển công việc theo thông tin bạn đã chọn.',
      details: [
        `Cảnh báo: ${alert.title}`,
        `Nhân viên nhận việc: ${candidate?.employee_name || 'Nhân viên đã chọn'}`,
        `Số công việc chuyển: ${Number(payload.tasks_to_transfer) || 1}`,
        `Ghi chú: ${payload.note?.trim() || 'Không thêm ghi chú'}`,
      ],
      confirmLabel: 'Áp dụng điều phối',
    })
    if (!confirmed) return
    setError('')
    try {
      const plan = await applyCoordination(alert.id, payload, coordinationIdempotencyKeyRef.current)
      applyCoordinationResult(alert, plan)
      notifyActionSuccess({
        title: 'Đã áp dụng phương án điều phối',
        message: `Đã chuyển ${plan.tasks_to_transfer} công việc cho ${plan.target_employee_name}.`,
        details: [
          `Cảnh báo: ${alert.title}`,
          plan.note ? `Ghi chú: ${plan.note}` : 'Không thêm ghi chú',
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể áp dụng phương án điều phối.'
      setError(message)
      notifyActionError({ title: 'Chưa áp dụng điều phối', message })
    }
  }

  function applyCoordinationResult(alert, plan) {
    const resolutionNote = `Đã áp dụng điều phối: chuyển ${plan.tasks_to_transfer} công việc cho ${plan.target_employee_name}.${plan.note ? ` Ghi chú: ${plan.note}` : ''}`
    setAlerts((current) =>
      current.map((item) =>
        item.id === alert.id
          ? {
              ...item,
              status: 'resolved',
              resolution_note: resolutionNote,
              resolved_by: plan.created_by,
              resolved_at: plan.created_at,
              updated_at: plan.updated_at,
            }
          : item,
      ),
    )
    setCoordinationSuggestions((current) => ({
      ...current,
      [alert.id]: {
        ...current[alert.id],
        applied_plan: plan,
      },
    }))
    setHighlightedAlertId(alert.id)
    setSelectedCoordination(null)
    coordinationIdempotencyKeyRef.current = null
  }

  function handleAiCoordinationApplied(alert, plan) {
    applyCoordinationResult(alert, plan)
  }

  function openCoordinationEditor(alert, suggestion) {
    const candidate = suggestion?.candidates?.[0]
    if (!candidate) return
    setCoordinationForm({
      target_employee_id: candidate.employee_id,
      tasks_to_transfer: '1',
      note: '',
    })
    coordinationIdempotencyKeyRef.current = generateIdempotencyKey()
    setSelectedCoordination({ alert, suggestion })
  }

  async function handleCoordinationSubmit(event) {
    event.preventDefault()
    if (!selectedCoordination) return
    await handleApplyCoordination(selectedCoordination.alert, {
      target_employee_id: coordinationForm.target_employee_id,
      tasks_to_transfer: Number(coordinationForm.tasks_to_transfer),
      note: coordinationForm.note,
    })
  }

  function openDepartmentDirective(summary) {
    setSelectedDepartment(summary)
    departmentDirectiveIdempotencyKeyRef.current = generateIdempotencyKey()
    setDepartmentDirectiveError('')
    setDepartmentDirectiveForm({ alert_type: 'all', severity: 'all', note: '' })
  }

  async function handleIssueDepartmentDirective(event) {
    event.preventDefault()
    if (
      !selectedDepartment ||
      selectedDepartmentOpenCount === 0 ||
      selectedDepartmentHasOverlappingDirective ||
      departmentDirectiveSaving
    ) {
      return
    }
    setDepartmentDirectiveSaving(true)
    setDepartmentDirectiveError('')
    try {
      const created = await issueDepartmentDirective(
        selectedDepartment.department_id,
        {
          alert_type: departmentDirectiveForm.alert_type,
          severity: departmentDirectiveForm.severity,
          note: departmentDirectiveForm.note,
        },
        departmentDirectiveIdempotencyKeyRef.current,
      )
      setDepartmentDirectives((current) => [
        created,
        ...current.filter((item) => item.id !== created.id),
      ])
      setSelectedDepartment(null)
      departmentDirectiveIdempotencyKeyRef.current = null
      notifyActionSuccess({
        title: 'Đã ra chỉ thị phòng ban',
        message: `Chỉ thị cho ${selectedDepartment.department_name} đã được tạo thành công.`,
        details: [
          `Loại cảnh báo: ${departmentDirectiveForm.alert_type === 'all' ? 'Tất cả loại' : departmentDirectiveForm.alert_type}`,
          `Mức độ: ${departmentDirectiveForm.severity === 'all' ? 'Tất cả mức độ' : departmentDirectiveForm.severity}`,
        ],
      })
    } catch (requestError) {
      const message = requestError.message || 'Không thể ra chỉ thị phòng ban.'
      setDepartmentDirectiveError(message)
      notifyActionError({ title: 'Chưa tạo chỉ thị phòng ban', message })
    } finally {
      setDepartmentDirectiveSaving(false)
    }
  }

  const clearBannerTimer = useCallback(() => {
    if (bannerTimerRef.current) {
      window.clearTimeout(bannerTimerRef.current)
      bannerTimerRef.current = null
    }
  }, [])

  const dismissNewAlertBanners = useCallback(() => {
    clearBannerTimer()
    bannerItemsRef.current = []
    lastBannerReceivedAtRef.current = 0
    isBannerVisibleRef.current = false
    setNewAlertBanners([])
  }, [clearBannerTimer])

  const scheduleBannerDismissal = useCallback(() => {
    clearBannerTimer()
    bannerTimerRef.current = window.setTimeout(() => {
      bannerItemsRef.current = []
      isBannerVisibleRef.current = false
      lastBannerReceivedAtRef.current = 0
      setNewAlertBanners([])
      bannerTimerRef.current = null
    }, 12000)
  }, [clearBannerTimer])

  const handleRealtimeAlert = useCallback(
    (message) => {
      invalidateResource('alerts')
      void loadAlerts()
      if (message?.operation !== 'insert') return

      const banner = mapRealtimeAlert(message.data)
      if (!banner) return

      const now = Date.now()
      const shouldMerge =
        isBannerVisibleRef.current && now - lastBannerReceivedAtRef.current <= 5000
      const nextBanners = shouldMerge ? [...bannerItemsRef.current, banner] : [banner]
      bannerItemsRef.current = nextBanners
      lastBannerReceivedAtRef.current = now
      isBannerVisibleRef.current = true
      setNewAlertBanners(nextBanners)
      scheduleBannerDismissal()
    },
    [loadAlerts, scheduleBannerDismissal],
  )

  async function handleViewNewestAlert() {
    const newestBanner = bannerItemsRef.current.at(-1)
    if (!newestBanner) return

    dismissNewAlertBanners()
    setStatusFilter('all')
    setSeverityFilter('all')
    setSearchTerm('')
    setHighlightedAlertId(newestBanner.id)
    await loadAlerts()
    scheduleAlertScroll(newestBanner.id)
  }

  function scheduleAlertScroll(alertId, attempt = 0) {
    if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current)
    const element = document.getElementById(`alert-card-${alertId}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    if (attempt >= 20) return
    scrollTimerRef.current = window.setTimeout(() => {
      scrollTimerRef.current = null
      scheduleAlertScroll(alertId, attempt + 1)
    }, 100)
  }

  useRealtimeUpdates('alerts', handleRealtimeAlert, {
    coalesceDelay: REALTIME_COALESCE_DELAY_MS,
  })
  useRealtimeUpdates(
    'department_directives',
    () => {
      if (role === 'leadership') void loadDepartmentDirectives()
    },
    { coalesceDelay: REALTIME_COALESCE_DELAY_MS },
  )

  const filteredAlerts = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLocaleLowerCase('vi-VN')
    return alerts.filter((alert) => {
      const matchesType = alertTypeFilter === 'all' || alert.alert_type === alertTypeFilter
      const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
      const matchesStatus = statusFilter === 'all' || alert.status === statusFilter
      const matchesEmployee = !employeeIdFilter || alert.employee_id === employeeIdFilter
      const matchesDepartment = !departmentIdFilter || alert.department_id === departmentIdFilter
      const searchableText = `${alert.employee_name} ${alert.employee_code}`.toLocaleLowerCase(
        'vi-VN',
      )
      return (
        matchesType &&
        matchesSeverity &&
        matchesStatus &&
        matchesEmployee &&
        matchesDepartment &&
        (!normalizedSearch || searchableText.includes(normalizedSearch))
      )
    })
  }, [
    alertTypeFilter,
    alerts,
    departmentIdFilter,
    employeeIdFilter,
    searchTerm,
    severityFilter,
    statusFilter,
  ])

  const openCount = alerts.filter((alert) => alert.status === 'open').length
  const highCount = alerts.filter((alert) => alert.severity === 'high').length
  const employeeGroups = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLocaleLowerCase('vi-VN')
    const groups = new Map()

    alerts.forEach((alert) => {
      const matchesType = alertTypeFilter === 'all' || alert.alert_type === alertTypeFilter
      const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
      const searchableText =
        `${alert.employee_name || ''} ${alert.employee_code || ''}`.toLocaleLowerCase('vi-VN')
      if (
        !matchesType ||
        !matchesSeverity ||
        (employeeIdFilter && alert.employee_id !== employeeIdFilter) ||
        (departmentIdFilter && alert.department_id !== departmentIdFilter) ||
        (normalizedSearch && !searchableText.includes(normalizedSearch))
      ) {
        return
      }

      const employeeId = alert.employee_id || `unknown-${alert.employee_name || alert.id}`
      if (!groups.has(employeeId)) {
        groups.set(employeeId, {
          employee_id: employeeId,
          employee_name: alert.employee_name || 'Chưa xác định',
          employee_code: alert.employee_code || 'Chưa có mã',
          openAlerts: [],
          resolvedAlerts: [],
        })
      }

      const group = groups.get(employeeId)
      if (alert.status === 'open') {
        group.openAlerts.push(alert)
      } else {
        group.resolvedAlerts.push(alert)
      }
    })

    return Array.from(groups.values()).sort((left, right) => {
      const leftHasHighOpen = left.openAlerts.some((alert) => alert.severity === 'high')
      const rightHasHighOpen = right.openAlerts.some((alert) => alert.severity === 'high')
      if (leftHasHighOpen !== rightHasHighOpen) return rightHasHighOpen - leftHasHighOpen

      return getLatestAlertTimestamp(right) - getLatestAlertTimestamp(left)
    })
  }, [alertTypeFilter, alerts, departmentIdFilter, employeeIdFilter, searchTerm, severityFilter])

  const visibleEmployeeGroups = useMemo(
    () =>
      employeeGroups.filter((group) => {
        if (statusFilter === 'open') return group.openAlerts.length > 0
        if (statusFilter === 'resolved') return group.resolvedAlerts.length > 0
        return group.openAlerts.length > 0 || group.resolvedAlerts.length > 0
      }),
    [employeeGroups, statusFilter],
  )
  const departmentDirectivesById = useMemo(() => {
    const grouped = {}
    departmentDirectives.forEach((directive) => {
      const current = grouped[directive.target_department_id] || []
      grouped[directive.target_department_id] = [...current, directive]
    })
    return grouped
  }, [departmentDirectives])
  const visibleDepartmentGroups = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLocaleLowerCase('vi-VN')
    return departmentSummaries
      .map((summary) => {
        const summaryAlerts = alerts.filter(
          (alert) =>
            alert.department_id === summary.department_id &&
            (!employeeIdFilter || alert.employee_id === employeeIdFilter),
        )
        const filtered = summaryAlerts.filter((alert) => {
          const matchesType = alertTypeFilter === 'all' || alert.alert_type === alertTypeFilter
          const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
          return matchesType && matchesSeverity
        })
        const useFilteredData =
          summaryAlerts.length > 0 && (alertTypeFilter !== 'all' || severityFilter !== 'all')
        const source = useFilteredData ? filtered : summaryAlerts
        const counts = useFilteredData
          ? {
              total: source.length,
              open: source.filter((alert) => alert.status === 'open').length,
              resolved: source.filter((alert) => alert.status === 'resolved').length,
              earlyWarning: source.filter((alert) => alert.alert_type === 'early_warning').length,
              overload: source.filter((alert) => alert.alert_type === 'overload').length,
              high: source.filter((alert) => alert.severity === 'high').length,
            }
          : {
              total: summary.total_count,
              open: summary.open_count,
              resolved: summary.resolved_count,
              earlyWarning: summary.early_warning_count,
              overload: summary.overload_count,
              high: summary.high_count,
            }
        return {
          ...summary,
          ...counts,
          departmentAlerts: filtered,
          matchesDepartment: !departmentIdFilter || summary.department_id === departmentIdFilter,
        }
      })
      .filter((summary) => {
        const matchesSearch =
          !normalizedSearch ||
          `${summary.department_name} ${summary.department_code || ''}`
            .toLocaleLowerCase('vi-VN')
            .includes(normalizedSearch)
        if (!matchesSearch || !summary.matchesDepartment) return false
        if (statusFilter === 'open') return summary.open > 0
        if (statusFilter === 'resolved') return summary.resolved > 0
        return summary.total > 0
      })
  }, [
    alertTypeFilter,
    alerts,
    departmentIdFilter,
    departmentSummaries,
    employeeIdFilter,
    searchTerm,
    severityFilter,
    statusFilter,
  ])
  const selectedDepartmentOpenCount = useMemo(() => {
    if (!selectedDepartment) return 0
    const directedAlertIds = new Set(
      (departmentDirectivesById[selectedDepartment.department_id] || []).flatMap(
        (directive) => directive.alert_ids || [],
      ),
    )
    const matching = alerts.filter(
      (alert) =>
        alert.department_id === selectedDepartment.department_id &&
        alert.status === 'open' &&
        DIRECTIVE_ALERT_TYPES.has(alert.alert_type) &&
        !directedAlertIds.has(alert.id) &&
        (departmentDirectiveForm.alert_type === 'all' ||
          alert.alert_type === departmentDirectiveForm.alert_type) &&
        (departmentDirectiveForm.severity === 'all' ||
          alert.severity === departmentDirectiveForm.severity),
    )
    return matching.length
  }, [alerts, departmentDirectiveForm, departmentDirectivesById, selectedDepartment])
  const selectedDepartmentHasOverlappingDirective = useMemo(() => {
    if (!selectedDepartment) return false
    return (departmentDirectivesById[selectedDepartment.department_id] || [])
      .filter((directive) => directive.status === 'pending')
      .some((directive) =>
        directiveFiltersOverlap(
          directive.selected_alert_type,
          directive.selected_severity,
          departmentDirectiveForm.alert_type,
          departmentDirectiveForm.severity,
        ),
      )
  }, [departmentDirectiveForm, departmentDirectivesById, selectedDepartment])
  const dailyAlertTrend = useMemo(() => buildDailyAlertTrend(alerts), [alerts])

  return (
    <MainLayout>
      <FadeIn className="mx-auto max-w-5xl">
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-amber-600">
                Theo dõi sớm
              </p>
              <h1 className="mt-2 text-slate-900">
                {role === 'leadership' ? 'Cảnh báo toàn công ty' : 'Cảnh báo hiệu suất'}
              </h1>
              <p className="mt-2 text-ink-600">
                Theo dõi cả dấu hiệu sớm và tình trạng quá tải cần xử lý ngay.
              </p>
            </div>
            <Button type="button" variant="secondary" onClick={handleScan} disabled={isScanning}>
              {isScanning ? 'Đang quét...' : 'Quét lại dữ liệu'}
            </Button>
          </div>

          <WeeklyAlertSparkline data={dailyAlertTrend} />

          {newAlertBanners.length > 0 && (
            <NewAlertBanner
              banners={newAlertBanners}
              onViewNewest={handleViewNewestAlert}
              onDismiss={dismissNewAlertBanners}
            />
          )}

          {error && <p className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

          {role === 'manager' && (
            <ManagerAlertDirectiveAction alerts={alerts} onCompleted={loadAlerts} />
          )}

          <div className="mt-6 grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              {role === 'leadership' ? 'Tìm phòng ban' : 'Tìm nhân viên'}
              <Input
                className="mt-1"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder={
                  role === 'leadership' ? 'Tên hoặc mã phòng ban' : 'Tên hoặc mã nhân viên'
                }
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Loại cảnh báo
              <Select
                className="mt-1"
                value={alertTypeFilter}
                onChange={(event) => setAlertTypeFilter(event.target.value)}
              >
                <option value="all">Tất cả loại</option>
                <option value="early_warning">Dấu hiệu sớm</option>
                <option value="overload">Quá tải</option>
              </Select>
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold">
            <FilterChip
              label="Tất cả"
              count={alerts.length}
              active={statusFilter === 'all' && severityFilter === 'all'}
              onClick={() => {
                setStatusFilter('all')
                setSeverityFilter('all')
              }}
            />
            <FilterChip
              label="chưa xử lý"
              count={openCount}
              active={statusFilter === 'open'}
              onClick={() => setStatusFilter(statusFilter === 'open' ? 'all' : 'open')}
              tone="amber"
            />
            <FilterChip
              label="đã xử lý"
              count={alerts.length - openCount}
              active={statusFilter === 'resolved'}
              onClick={() => setStatusFilter(statusFilter === 'resolved' ? 'all' : 'resolved')}
              tone="slate"
            />
            <FilterChip
              label="mức cao"
              count={highCount}
              active={severityFilter === 'high'}
              onClick={() => setSeverityFilter(severityFilter === 'high' ? 'all' : 'high')}
              tone="red"
            />
            <span className="self-center text-slate-500">
              {role === 'leadership'
                ? `${visibleDepartmentGroups.reduce((sum, group) => sum + group.total, 0)}/${alerts.length} cảnh báo đang hiển thị`
                : `${filteredAlerts.length}/${alerts.length} cảnh báo đang hiển thị`}
            </span>
          </div>

          <div className="mt-6 space-y-4">
            {isLoading && <p className="text-sm text-slate-500">Đang tải cảnh báo...</p>}
            {!isLoading &&
              !departmentSummaryLoading &&
              role === 'leadership' &&
              !visibleDepartmentGroups.length && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
                  {alerts.length
                    ? 'Không có cảnh báo phù hợp với bộ lọc hiện tại.'
                    : 'Chưa có cảnh báo nào trong phạm vi của bạn.'}
                </div>
              )}
            {role === 'leadership' ? (
              departmentSummaryLoading ? (
                <p className="text-sm text-slate-500">Đang tải tổng hợp cảnh báo...</p>
              ) : (
                <AnimatePresence initial={false} mode="popLayout">
                  {visibleDepartmentGroups.map((group) => (
                    <FadeIn key={group.department_id} layout>
                      <DepartmentAlertGroup
                        summary={group}
                        departmentAlerts={group.departmentAlerts}
                        directives={departmentDirectivesById[group.department_id]}
                        statusFilter={statusFilter}
                        focusedAlertId={focusedAlertId}
                        highlightedAlertId={highlightedAlertId}
                        onIssueDirective={openDepartmentDirective}
                      />
                    </FadeIn>
                  ))}
                </AnimatePresence>
              )
            ) : (
              <AnimatePresence initial={false} mode="popLayout">
                {visibleEmployeeGroups.map((group) => (
                  <FadeIn key={group.employee_id} layout>
                    <EmployeeAlertGroup
                      employeeName={group.employee_name}
                      employeeCode={group.employee_code}
                      openAlerts={group.openAlerts}
                      resolvedAlerts={group.resolvedAlerts}
                      statusFilter={statusFilter}
                      coordinationSuggestions={coordinationSuggestions}
                      highlightedAlertId={highlightedAlertId}
                      focusedAlertId={focusedAlertId}
                      resolvingIds={resolvingIds}
                      onResolve={(alert) => setSelectedAlert(alert)}
                      onQuickResolve={handleQuickResolve}
                      onApplyCoordination={handleApplyCoordination}
                      onAiResolved={applyResolvedAlert}
                      onAiCoordinationApplied={handleAiCoordinationApplied}
                      onEditCoordination={openCoordinationEditor}
                      role={role}
                    />
                  </FadeIn>
                ))}
              </AnimatePresence>
            )}
          </div>
        </section>
      </FadeIn>

      {selectedAlert && (
        <Modal
          title="Ghi nhận xử lý cảnh báo"
          description={`Cập nhật cách xử lý cho ${selectedAlert.employee_name}.`}
          onClose={() => setSelectedAlert(null)}
        >
          <form className="space-y-4" onSubmit={handleResolve}>
            <label className="block text-sm font-medium text-slate-700">
              Ghi chú xử lý
              <Textarea
                className="mt-1 min-h-32"
                value={resolutionNote}
                onChange={(event) => setResolutionNote(event.target.value)}
                placeholder="Ví dụ: Đã phân bổ bớt công việc cho nhân viên khác."
              />
            </label>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setSelectedAlert(null)}>
                Hủy
              </Button>
              <Button type="submit" disabled={isSaving} loading={isSaving}>
                {isSaving ? 'Đang lưu...' : 'Xác nhận đã xử lý'}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {selectedCoordination && (
        <Modal
          title="Chỉnh sửa gợi ý điều phối"
          description={`Chọn nhân viên cùng phòng để nhận bớt việc từ ${selectedCoordination.alert.employee_name}.`}
          onClose={() => setSelectedCoordination(null)}
        >
          <form className="space-y-4" onSubmit={handleCoordinationSubmit}>
            <label className="block text-sm font-medium text-slate-700">
              Nhân viên nhận việc
              <Select
                className="mt-1"
                value={coordinationForm.target_employee_id}
                onChange={(event) =>
                  setCoordinationForm((current) => {
                    const candidate = selectedCoordination.suggestion.candidates.find(
                      (item) => item.employee_id === event.target.value,
                    )
                    const transferLimit = getCandidateTransferLimit(candidate)
                    return {
                      ...current,
                      target_employee_id: event.target.value,
                      tasks_to_transfer: String(
                        Math.min(Number(current.tasks_to_transfer) || 1, transferLimit || 1),
                      ),
                    }
                  })
                }
              >
                {selectedCoordination.suggestion.candidates.map((candidate) => (
                  <option key={candidate.employee_id} value={candidate.employee_id}>
                    {candidate.employee_name} ({candidate.employee_code}) —{' '}
                    {formatCandidateWorkload(candidate)}
                  </option>
                ))}
              </Select>
            </label>
            {formatActiveTaskTitles(
              selectedCoordination.suggestion.candidates.find(
                (candidate) => candidate.employee_id === coordinationForm.target_employee_id,
              ),
            ) && (
              <p className="-mt-2 text-xs leading-5 text-slate-500">
                {formatActiveTaskTitles(
                  selectedCoordination.suggestion.candidates.find(
                    (candidate) => candidate.employee_id === coordinationForm.target_employee_id,
                  ),
                )}
              </p>
            )}
            <label className="block text-sm font-medium text-slate-700">
              Số công việc điều phối
              <Select
                className="mt-1"
                value={coordinationForm.tasks_to_transfer}
                onChange={(event) =>
                  setCoordinationForm((current) => ({
                    ...current,
                    tasks_to_transfer: event.target.value,
                  }))
                }
              >
                {Array.from(
                  {
                    length: getCandidateTransferLimit(
                      selectedCoordination.suggestion.candidates.find(
                        (candidate) =>
                          candidate.employee_id === coordinationForm.target_employee_id,
                      ),
                    ),
                  },
                  (_, index) => index + 1,
                ).map((count) => (
                  <option key={count} value={count}>
                    {count} công việc
                  </option>
                ))}
              </Select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Ghi chú điều phối
              <Textarea
                className="mt-1 min-h-24"
                value={coordinationForm.note}
                onChange={(event) =>
                  setCoordinationForm((current) => ({
                    ...current,
                    note: event.target.value,
                  }))
                }
                placeholder="Ví dụ: Chuyển các việc ưu tiên thấp trong ngày hôm nay."
              />
            </label>
            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setSelectedCoordination(null)}
              >
                Hủy
              </Button>
              <Button type="submit">Áp dụng phương án đã chỉnh sửa</Button>
            </div>
          </form>
        </Modal>
      )}

      {selectedDepartment && (
        <Modal
          title={`Ra chỉ thị cho ${selectedDepartment.department_name}`}
          description="Chọn nhóm cảnh báo đang mở để Manager phòng ban tiếp nhận và xử lý."
          onClose={() => !departmentDirectiveSaving && setSelectedDepartment(null)}
        >
          <form className="space-y-4" onSubmit={handleIssueDepartmentDirective}>
            {departmentDirectiveError && (
              <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {departmentDirectiveError}
              </p>
            )}
            <label className="block text-sm font-medium text-slate-700">
              Loại cảnh báo
              <Select
                className="mt-1"
                value={departmentDirectiveForm.alert_type}
                onChange={(event) =>
                  setDepartmentDirectiveForm((current) => ({
                    ...current,
                    alert_type: event.target.value,
                  }))
                }
              >
                <option value="all">Tất cả loại</option>
                <option value="early_warning">Dấu hiệu sớm</option>
                <option value="overload">Quá tải</option>
              </Select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Mức độ cảnh báo
              <Select
                className="mt-1"
                value={departmentDirectiveForm.severity}
                onChange={(event) =>
                  setDepartmentDirectiveForm((current) => ({
                    ...current,
                    severity: event.target.value,
                  }))
                }
              >
                <option value="all">Tất cả mức độ</option>
                <option value="medium">Mức trung bình</option>
                <option value="high">Mức cao</option>
              </Select>
            </label>
            {selectedDepartmentHasOverlappingDirective ? (
              <p className="rounded-lg bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                Phòng ban đã có chỉ thị đang chờ cho nhóm cảnh báo này. Bạn có thể chọn nhóm khác.
              </p>
            ) : selectedDepartmentOpenCount === 0 ? (
              <p className="rounded-lg bg-amber-50 p-3 text-sm font-semibold text-amber-900">
                Không có cảnh báo đang mở phù hợp để phát hành chỉ thị.
              </p>
            ) : (
              <p className="rounded-lg bg-blue-50 p-3 text-sm font-semibold text-blue-900">
                Có {selectedDepartmentOpenCount} cảnh báo đang mở phù hợp với lựa chọn.
              </p>
            )}
            <label className="block text-sm font-medium text-slate-700">
              Ghi chú chỉ thị (tùy chọn)
              <Textarea
                className="mt-1 min-h-24"
                maxLength={1000}
                value={departmentDirectiveForm.note}
                onChange={(event) =>
                  setDepartmentDirectiveForm((current) => ({
                    ...current,
                    note: event.target.value,
                  }))
                }
                placeholder="Nêu rõ việc cần Manager rà soát hoặc hành động ưu tiên."
              />
            </label>
            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setSelectedDepartment(null)}
                disabled={departmentDirectiveSaving}
              >
                Hủy
              </Button>
              <Button
                type="submit"
                disabled={
                  departmentDirectiveSaving ||
                  selectedDepartmentOpenCount === 0 ||
                  selectedDepartmentHasOverlappingDirective
                }
                loading={departmentDirectiveSaving}
              >
                {departmentDirectiveSaving ? 'Đang gửi...' : 'Gửi chỉ thị'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </MainLayout>
  )
}

function NewAlertBanner({ banners, onViewNewest, onDismiss }) {
  const newestBanner = banners.at(-1)
  const count = banners.length
  const hasHighSeverity = banners.some((banner) => banner.severity === 'high')

  return (
    <div
      role="status"
      aria-live="polite"
      className={`sticky top-4 z-20 mt-5 rounded-xl border px-4 py-3 shadow-lg transition-colors duration-motion-standard ease-motion-standard sm:px-5 ${
        hasHighSeverity
          ? 'border-red-300 bg-red-50 text-red-900'
          : 'border-amber-300 bg-amber-50 text-amber-900'
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-lg ${
            hasHighSeverity ? 'bg-red-100' : 'bg-amber-100'
          }`}
          aria-hidden="true"
        >
          !
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-bold">
            {count > 1 ? `Có ${count} cảnh báo mới` : 'Có 1 cảnh báo mới'}
          </p>
          <p className="mt-1 truncate text-sm opacity-85">
            {newestBanner?.employeeName} · {newestBanner?.title}
          </p>
          <p className="mt-1 text-xs opacity-70">
            Cập nhật lúc {formatDateTime(newestBanner?.timestamp)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            className={`rounded-lg px-3 py-2 text-xs font-bold transition duration-motion-micro ease-motion-standard ${
              hasHighSeverity
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-amber-500 text-white hover:bg-amber-600'
            }`}
            onClick={onViewNewest}
          >
            Xem ngay
          </button>
          <button
            type="button"
            className="rounded-lg px-2 py-2 text-lg leading-none opacity-70 transition duration-motion-micro ease-motion-standard hover:bg-black/5 hover:opacity-100"
            onClick={onDismiss}
            aria-label="Đóng thông báo cảnh báo mới"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  )
}

function WeeklyAlertSparkline({ data }) {
  const total = data.reduce((sum, day) => sum + day.count, 0)

  return (
    <div className="mt-4 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-600">
            Xu hướng cảnh báo theo ngày
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Số cảnh báo được tạo từng ngày trong 8 tuần gần nhất.
          </p>
        </div>
        <span className="shrink-0 text-xs font-semibold text-slate-500">{total} cảnh báo</span>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Số trên cột là số cảnh báo trong ngày; di chuột vào từng cột để xem ngày cụ thể.
      </p>
      <div className="mt-4 w-full overflow-x-auto pb-1">
        <div
          className="flex h-32 min-w-[42rem] items-end gap-0.5 sm:gap-1"
          aria-label="Biểu đồ số cảnh báo theo từng ngày"
        >
          {data.map((day, index) => (
            <div
              key={day.key}
              className={`flex h-full min-w-0 flex-1 flex-col items-center justify-end ${
                day.isWeekStart ? 'border-l border-slate-200 pl-0.5' : ''
              }`}
            >
              <div className="flex h-24 w-full flex-col items-center justify-end">
                <span className="mb-1 h-3 text-[9px] font-bold leading-3 text-brand-700">
                  {day.count > 0 ? day.count : ''}
                </span>
                <div
                  className={`alert-trend-bar w-full rounded-t-md transition-all duration-motion-standard ease-motion-standard hover:bg-brand-700 ${
                    day.count > 0 ? 'bg-brand-500' : 'bg-slate-200'
                  }`}
                  style={{
                    height: `${day.height}%`,
                    '--trend-delay': `${Math.min(index * 18, 450)}ms`,
                  }}
                  title={`${day.fullLabel}: ${day.count} cảnh báo`}
                  aria-label={`${day.fullLabel}: ${day.count} cảnh báo`}
                />
              </div>
              <span className="mt-1 h-3 truncate text-[9px] leading-3 text-slate-400">
                {day.isWeekStart ? day.label : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function DepartmentAlertGroup({
  summary,
  departmentAlerts = [],
  directives = [],
  statusFilter = 'all',
  focusedAlertId,
  highlightedAlertId,
  onIssueDirective,
}) {
  const [cardStatusFilter, setCardStatusFilter] = useState(statusFilter)
  useEffect(() => {
    setCardStatusFilter(statusFilter)
  }, [statusFilter])
  const isFocused = summary.alert_ids?.includes(focusedAlertId)
  const isHighlighted = summary.alert_ids?.includes(highlightedAlertId)
  const hasAlertDetails = departmentAlerts.length > 0
  const directedAlertIds = new Set(directives.flatMap((directive) => directive.alert_ids || []))
  const openAlerts = departmentAlerts.filter((alert) => alert.status === 'open')
  const unsentAlerts = openAlerts.filter(
    (alert) => DIRECTIVE_ALERT_TYPES.has(alert.alert_type) && !directedAlertIds.has(alert.id),
  )
  const sentAlerts = departmentAlerts.filter((alert) => directedAlertIds.has(alert.id))
  const visibleDetails =
    cardStatusFilter === 'undirected'
      ? unsentAlerts
      : cardStatusFilter === 'directed'
        ? sentAlerts
        : departmentAlerts.filter(
            (alert) => cardStatusFilter === 'all' || alert.status === cardStatusFilter,
          )
  // Chỉ cảnh báo quá tải và dấu hiệu sớm mới đủ điều kiện phát chỉ thị.
  // Khi chưa có dữ liệu chi tiết, giữ nút ở trạng thái an toàn là vô hiệu hóa.
  const undirectedOpenCount = hasAlertDetails ? unsentAlerts.length : 0
  // Một chỉ thị có thể bao gồm nhiều cảnh báo. Chip này đếm bản ghi chỉ thị,
  // còn danh sách `sentAlerts` vẫn dùng để lọc các cảnh báo nằm trong chỉ thị.
  const directedDirectiveCount = directives.length
  const statusLabel =
    cardStatusFilter === 'undirected'
      ? 'Chưa gửi chỉ thị'
      : cardStatusFilter === 'directed'
        ? 'Đã gửi chỉ thị'
        : cardStatusFilter === 'open'
          ? 'Chưa xử lý'
          : cardStatusFilter === 'resolved'
            ? 'Đã xử lý'
            : 'Tất cả trạng thái'
  const metricData = [
    {
      key: 'early_warning',
      label: 'Dấu hiệu sớm',
      tone: 'amber',
      count: getDepartmentMetricCount(
        summary,
        'earlyWarning',
        cardStatusFilter,
        visibleDetails,
        hasAlertDetails,
        'early_warning',
      ),
    },
    {
      key: 'overload',
      label: 'Quá tải',
      tone: 'red',
      count: getDepartmentMetricCount(
        summary,
        'overload',
        cardStatusFilter,
        visibleDetails,
        hasAlertDetails,
        'overload',
      ),
    },
    {
      key: 'high',
      label: 'Mức cao',
      tone: 'red',
      count: getDepartmentMetricCount(
        summary,
        'high',
        cardStatusFilter,
        visibleDetails,
        hasAlertDetails,
        'high',
      ),
    },
  ]

  return (
    <article
      id={`department-alert-card-${summary.department_id}`}
      className={`rounded-2xl border p-5 transition-colors duration-motion-standard ease-motion-standard sm:p-6 ${
        isHighlighted || isFocused
          ? 'border-brand-400 bg-brand-50/40 ring-2 ring-brand-200'
          : 'border-slate-200 bg-slate-50/60'
      }`}
    >
      {summary.alert_ids?.map((alertId) => (
        <span key={alertId} id={`alert-card-${alertId}`} className="sr-only" />
      ))}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-lg font-bold text-slate-900">{summary.department_name}</p>
          <p className="mt-1 text-sm text-slate-500">
            Mã phòng ban: {summary.department_code || 'Chưa có mã'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <DepartmentStatusFilter
            label="cảnh báo"
            count={summary.total}
            active={cardStatusFilter === 'all'}
            onClick={() => setCardStatusFilter('all')}
          />
          <DepartmentStatusFilter
            label="chưa xử lý"
            count={summary.open}
            active={cardStatusFilter === 'open'}
            tone="amber"
            onClick={() => setCardStatusFilter('open')}
          />
          <DepartmentStatusFilter
            label="đã xử lý"
            count={summary.resolved}
            active={cardStatusFilter === 'resolved'}
            tone="emerald"
            onClick={() => setCardStatusFilter('resolved')}
          />
          <DepartmentStatusFilter
            label="chưa gửi chỉ thị"
            count={undirectedOpenCount}
            active={cardStatusFilter === 'undirected'}
            tone="amber"
            onClick={() => setCardStatusFilter('undirected')}
          />
          <DepartmentStatusFilter
            label="chỉ thị đã gửi"
            count={directedDirectiveCount}
            active={cardStatusFilter === 'directed'}
            tone="blue"
            onClick={() => setCardStatusFilter('directed')}
          />
        </div>
      </div>

      {directives.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
          <span className="font-bold">Chỉ thị đã gửi:</span>
          {directives.map((directive) => (
            <span key={directive.id} className="rounded-full bg-white px-2.5 py-1 font-semibold">
              {formatDepartmentDirectiveFilter(directive.selected_alert_type)} ·{' '}
              {formatDepartmentDirectiveFilter(directive.selected_severity)} ·{' '}
              {getDirectiveStatusLabel('alert', directive.status)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        {metricData.map((metric) => (
          <DepartmentMetric
            key={metric.key}
            label={metric.label}
            value={metric.count}
            tone={metric.tone}
            statusLabel={statusLabel}
            employeeNames={getDepartmentMetricEmployees(visibleDetails, metric.key)}
          />
        ))}
        <DepartmentMetric
          label="Mới nhất"
          value={formatDateTime(summary.latest_created_at)}
          tone="slate"
          statusLabel="Cập nhật gần nhất"
        />
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
        <p className="text-sm text-slate-600">
          Chỉ thị sẽ được gửi trực tiếp đến Quản lý của phòng ban này.
        </p>
        <button
          type="button"
          className="primary-button"
          disabled={undirectedOpenCount === 0}
          onClick={() => onIssueDirective(summary)}
        >
          Ra chỉ thị cho Quản lý
        </button>
      </div>
    </article>
  )
}

function DepartmentStatusFilter({ label, count, active, tone = 'slate', onClick }) {
  const toneClasses = {
    slate: active
      ? 'border-brand-500 bg-brand-50 text-brand-800 ring-1 ring-brand-500'
      : 'border-slate-200 bg-white text-slate-700 hover:border-brand-400',
    amber: active
      ? 'border-amber-500 bg-amber-100 text-amber-900 ring-1 ring-amber-500'
      : 'border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-400',
    emerald: active
      ? 'border-emerald-500 bg-emerald-100 text-emerald-900 ring-1 ring-emerald-500'
      : 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:border-emerald-400',
    blue: active
      ? 'border-blue-500 bg-blue-100 text-blue-900 ring-1 ring-blue-500'
      : 'border-blue-200 bg-blue-50 text-blue-800 hover:border-blue-400',
  }

  return (
    <button
      type="button"
      className={`rounded-full border px-3 py-1.5 transition duration-motion-micro ease-motion-standard ${toneClasses[tone]}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {count} {label}
    </button>
  )
}

function DepartmentMetric({ label, value, tone, statusLabel, employeeNames = [] }) {
  const toneClasses = {
    amber: 'bg-amber-50 text-amber-900',
    red: 'bg-red-50 text-red-900',
    slate: 'bg-white text-slate-700',
  }
  const canShowEmployees = tone !== 'slate'
  return (
    <div className="group relative">
      <div
        tabIndex={canShowEmployees ? 0 : undefined}
        className={`rounded-xl p-3 outline-none ${toneClasses[tone]} ${canShowEmployees ? 'focus:ring-2 focus:ring-brand-300' : ''}`}
      >
        <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</p>
        <p className="mt-1 text-sm font-bold">{value}</p>
        <p className="mt-1 text-xs font-medium opacity-65">{statusLabel}</p>
      </div>
      {canShowEmployees && (
        <div className="invisible absolute left-0 top-full z-30 mt-2 w-64 translate-y-1 rounded-xl border border-slate-200 bg-white p-3 text-left opacity-0 shadow-xl transition duration-motion-micro ease-motion-standard group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
          <p className="text-xs font-bold text-slate-800">Nhân viên liên quan</p>
          {employeeNames.length ? (
            <ul className="mt-2 space-y-1 text-xs text-slate-600">
              {employeeNames.slice(0, 8).map((employee) => (
                <li key={employee.key} className="truncate">
                  {employee.name}
                  {employee.code ? ` · ${employee.code}` : ''}
                </li>
              ))}
              {employeeNames.length > 8 && (
                <li className="font-semibold text-brand-700">
                  +{employeeNames.length - 8} nhân viên khác
                </li>
              )}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-slate-500">Chưa có dữ liệu nhân viên phù hợp.</p>
          )}
        </div>
      )}
    </div>
  )
}

function getDepartmentMetricCount(
  summary,
  summaryKey,
  statusFilter,
  visibleDetails,
  hasAlertDetails,
  alertType,
) {
  if (hasAlertDetails) {
    return visibleDetails.filter((alert) =>
      alertType === 'high' ? alert.severity === 'high' : alert.alert_type === alertType,
    ).length
  }
  if (statusFilter === 'all') return summary[summaryKey]
  return 0
}

function getDepartmentMetricEmployees(alerts, metricKey) {
  const matching = alerts.filter((alert) =>
    metricKey === 'high' ? alert.severity === 'high' : alert.alert_type === metricKey,
  )
  const uniqueEmployees = new Map()
  matching.forEach((alert) => {
    const key = alert.employee_id || alert.employee_code || alert.employee_name
    if (!uniqueEmployees.has(key)) {
      uniqueEmployees.set(key, {
        key,
        name: alert.employee_name || 'Nhân viên chưa xác định',
        code: alert.employee_code,
      })
    }
  })
  return Array.from(uniqueEmployees.values())
}

function EmployeeAlertGroup({
  employeeName,
  employeeCode,
  openAlerts,
  resolvedAlerts,
  statusFilter,
  coordinationSuggestions,
  highlightedAlertId,
  focusedAlertId,
  resolvingIds,
  onResolve,
  onQuickResolve,
  onApplyCoordination,
  onAiResolved,
  onAiCoordinationApplied,
  onEditCoordination,
  role,
}) {
  const hasFocusedAlert = [...openAlerts, ...resolvedAlerts].some(
    (alert) => alert.id === focusedAlertId,
  )
  const [isCollapsed, setIsCollapsed] = useState(() => {
    if (hasFocusedAlert) return false
    if (statusFilter === 'resolved') return resolvedAlerts.length === 0
    if (statusFilter === 'open') return openAlerts.length === 0
    // Bộ lọc "Tất cả" phải hiển thị cả nhóm chỉ có cảnh báo đã xử lý.
    return false
  })
  const showOpen = statusFilter !== 'resolved'
  const showResolved = statusFilter !== 'open'
  const showBothColumns = showOpen && showResolved

  useEffect(() => {
    if (hasFocusedAlert) {
      setIsCollapsed(false)
    } else if (statusFilter === 'resolved') {
      // Khi lọc "Đã xử lý", nhóm phải mở nếu có cảnh báo đã xử lý.
      setIsCollapsed(resolvedAlerts.length === 0)
    } else if (statusFilter === 'open') {
      setIsCollapsed(openAlerts.length === 0)
    }
  }, [hasFocusedAlert, openAlerts.length, resolvedAlerts.length, statusFilter])

  function renderAlert(alert) {
    return (
      <FadeIn key={alert.id} layout>
        <AlertCard
          id={`alert-card-${alert.id}`}
          alert={alert}
          onResolve={() => onResolve(alert)}
          coordination={coordinationSuggestions[alert.id]}
          isJustProcessed={highlightedAlertId === alert.id}
          onApplyCoordination={() => onApplyCoordination(alert)}
          onAiResolved={onAiResolved}
          onAiCoordinationApplied={(plan) => onAiCoordinationApplied(alert, plan)}
          onEditCoordination={() => onEditCoordination(alert, coordinationSuggestions[alert.id])}
          onQuickResolve={() => onQuickResolve(alert)}
          isResolving={resolvingIds.has(alert.id)}
          role={role}
        />
      </FadeIn>
    )
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{employeeName}</h2>
          <p className="mt-1 text-sm text-slate-500">Mã nhân viên: {employeeCode}</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
            {openAlerts.length + resolvedAlerts.length} cảnh báo · {resolvedAlerts.length} đã xử lý
          </span>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition duration-motion-micro ease-motion-standard hover:border-brand-400 hover:text-brand-700"
            onClick={() => setIsCollapsed((current) => !current)}
            aria-expanded={!isCollapsed}
            aria-label={`${isCollapsed ? 'Xem chi tiết' : 'Thu gọn'} cảnh báo của ${employeeName}`}
          >
            {isCollapsed ? 'Xem chi tiết' : 'Thu gọn'}
            <svg
              aria-hidden="true"
              className={`h-4 w-4 transition-transform duration-motion-micro ease-motion-standard ${isCollapsed ? '' : 'rotate-180'}`}
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <div className={`mt-4 grid grid-cols-1 gap-4 ${showBothColumns ? 'md:grid-cols-2' : ''}`}>
            {showOpen && (
              <div className="min-w-0 rounded-xl border border-amber-200 bg-white p-3 sm:p-4">
                <h3 className="mb-3 text-sm font-bold text-amber-900">
                  Chưa xử lý ({openAlerts.length})
                </h3>
                <div className="space-y-3">
                  {openAlerts.length ? (
                    <AnimatePresence initial={false} mode="popLayout">
                      {openAlerts.map(renderAlert)}
                    </AnimatePresence>
                  ) : (
                    <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-400">
                      Không có cảnh báo chưa xử lý
                    </p>
                  )}
                </div>
              </div>
            )}

            {showResolved && (
              <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 sm:p-4">
                <h3 className="mb-3 text-sm font-bold text-slate-700">
                  Đã xử lý ({resolvedAlerts.length})
                </h3>
                <div className="space-y-3">
                  {resolvedAlerts.length ? (
                    <AnimatePresence initial={false} mode="popLayout">
                      {resolvedAlerts.map(renderAlert)}
                    </AnimatePresence>
                  ) : (
                    <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-400">
                      Không có cảnh báo đã xử lý
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </AnimatePresence>
    </section>
  )
}

function AlertCard({
  id,
  alert,
  onResolve,
  coordination,
  onApplyCoordination,
  onAiResolved,
  onAiCoordinationApplied,
  onEditCoordination,
  isJustProcessed = false,
  onQuickResolve,
  isResolving = false,
  role,
}) {
  const isResolved = alert.status === 'resolved'
  const isHigh = alert.severity === 'high'
  const severityLabel = isHigh ? 'Mức cao' : 'Mức trung bình'
  const alertTypeLabel = alert.alert_type === 'overload' ? 'Quá tải' : 'Dấu hiệu sớm'
  return (
    <article
      id={id}
      className={`rounded-xl border border-l-4 p-5 ${
        isJustProcessed
          ? 'border-emerald-300 border-l-emerald-500 bg-emerald-50 ring-2 ring-emerald-200 transition-colors duration-motion-standard ease-motion-standard'
          : isResolved
            ? 'border-slate-200 border-l-slate-300 bg-white'
            : isHigh
              ? 'border-slate-200 border-l-red-500 bg-white'
              : 'border-slate-200 border-l-amber-500 bg-white'
      }`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                isHigh ? 'bg-red-200 text-red-900' : 'bg-amber-200 text-amber-900'
              }`}
            >
              {severityLabel}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
              <AlertTypeIcon alertType={alert.alert_type} />
              {alertTypeLabel}
            </span>
            <span className="text-xs text-slate-500">{isResolved ? 'Đã xử lý' : 'Chưa xử lý'}</span>
          </div>
          <h2 className="mt-3 text-slate-900">{alert.title}</h2>
          <p className="mt-1 text-sm font-semibold text-slate-700">
            {alert.employee_name} · {alert.employee_code}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-700">{alert.message}</p>
          {Array.isArray(alert.detected_dates) && alert.detected_dates.length > 1 && (
            <div
              className="mt-3 flex flex-wrap items-center gap-2"
              aria-label="Các ngày phát hiện cảnh báo"
            >
              <span className="text-xs font-semibold text-slate-500">Diễn biến:</span>
              <div className="flex items-center">
                {alert.detected_dates.map((date, index) => (
                  <div key={`${date}-${index}`} className="flex items-center">
                    <span
                      className={`h-2.5 w-2.5 rounded-full ring-2 ring-white ${
                        isHigh ? 'bg-red-500' : 'bg-amber-500'
                      }`}
                      title={formatDetectedDate(date)}
                      aria-label={formatDetectedDate(date)}
                    />
                    {index < alert.detected_dates.length - 1 && (
                      <span className="h-px w-4 bg-slate-300" aria-hidden="true" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className={`mt-3 text-sm leading-6 ${isHigh ? 'text-red-950' : 'text-amber-950'}`}>
            <span className="font-semibold">Gợi ý:</span> {alert.suggested_action}
          </p>
          {alert.resolution_note && (
            <p className="mt-3 text-sm text-slate-600">
              <span className="font-semibold">Ghi chú xử lý:</span> {alert.resolution_note}
            </p>
          )}
          {alert.resolved_at && (
            <p className="mt-2 text-xs text-slate-500">
              Thời gian xử lý: {formatDateTime(alert.resolved_at)}
            </p>
          )}
          {role === 'manager' && coordination?.applied_plan ? (
            <p className="mt-3 text-sm font-semibold text-emerald-700">
              Đã áp dụng điều phối: chuyển {coordination.applied_plan.tasks_to_transfer} công việc
              cho {coordination.applied_plan.target_employee_name}.
            </p>
          ) : role === 'manager' && coordination?.candidates?.length > 0 && !isResolved ? (
            <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-3">
              <p className="text-sm font-semibold text-sky-900">Gợi ý điều phối trong phòng</p>
              <p className="mt-1 text-sm text-sky-800">
                Có thể chuyển việc cho {coordination.candidates[0].employee_name} —{' '}
                {formatCandidateWorkload(coordination.candidates[0])} và điểm chất lượng{' '}
                {coordination.candidates[0].quality_score}.
              </p>
              {formatActiveTaskTitles(coordination.candidates[0]) && (
                <p className="mt-2 text-xs text-sky-700">
                  {formatActiveTaskTitles(coordination.candidates[0])}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="primary-button" onClick={onApplyCoordination}>
                  Áp dụng gợi ý điều phối
                </button>
                <button type="button" className="secondary-button" onClick={onEditCoordination}>
                  Chỉnh sửa gợi ý
                </button>
              </div>
            </div>
          ) : null}
          <AiAlertProposalCard
            alert={alert}
            coordination={coordination}
            role={role}
            onResolved={onAiResolved}
            onCoordinationApplied={onAiCoordinationApplied}
          />
        </div>
        {!isResolved && onResolve && (
          <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col sm:items-stretch">
            {onQuickResolve && (
              <button
                type="button"
                className="secondary-button whitespace-nowrap text-xs"
                onClick={onQuickResolve}
                disabled={isResolving}
                aria-label={`Xử lý nhanh cảnh báo ${alert.title}`}
              >
                {isResolving ? 'Đang xử lý...' : 'Xử lý nhanh'}
              </button>
            )}
            <button
              type="button"
              className="secondary-button whitespace-nowrap"
              onClick={onResolve}
            >
              Đã xử lý
            </button>
          </div>
        )}
      </div>
    </article>
  )
}

function getLatestAlertTimestamp(group) {
  return [...group.openAlerts, ...group.resolvedAlerts].reduce(
    (latest, alert) => Math.max(latest, parseAlertTimestamp(alert.created_at)),
    0,
  )
}

function parseAlertTimestamp(value) {
  const timestamp = value ? new Date(value).getTime() : 0
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function mapRealtimeAlert(data) {
  if (!data || data._id === undefined || data._id === null) return null

  return {
    id: String(data._id),
    employeeName: data.employee_name || 'Nhân viên chưa xác định',
    severity: data.severity === 'high' ? 'high' : 'medium',
    alertType: data.alert_type === 'overload' ? 'overload' : 'early_warning',
    title: data.title || 'Cảnh báo mới',
    timestamp: data.created_at || new Date().toISOString(),
  }
}

function buildDailyAlertTrend(alerts) {
  const currentDayStart = getStartOfLocalDay(new Date())
  const days = Array.from({ length: 56 }, (_, index) => {
    const dayStart = new Date(currentDayStart)
    dayStart.setDate(currentDayStart.getDate() - (55 - index))
    return {
      key: getLocalDateKey(dayStart),
      label: formatDateOnly(dayStart),
      fullLabel: formatDetectedDate(dayStart),
      count: 0,
      isWeekStart: index % 7 === 0,
    }
  })
  const dayByKey = new Map(days.map((day) => [day.key, day]))

  alerts.forEach((alert) => {
    const timestamp = parseAlertTimestamp(alert.created_at)
    if (!timestamp) return
    const day = dayByKey.get(getLocalDateKey(new Date(timestamp)))
    if (day) day.count += 1
  })

  const maximum = Math.max(...days.map((day) => day.count), 1)
  return days.map((day) => ({
    ...day,
    height: day.count ? Math.max(12, Math.round((day.count / maximum) * 100)) : 4,
  }))
}

function getStartOfLocalDay(value) {
  const date = new Date(value)
  date.setHours(0, 0, 0, 0)
  return date
}

function getLocalDateKey(value) {
  const date = getStartOfLocalDay(value)
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

function formatDateOnly(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không xác định'
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
  }).format(date)
}

function formatDetectedDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value || 'Ngày không xác định')
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

function FilterChip({ label, count, active, onClick, tone = 'brand' }) {
  const toneClasses = {
    amber: active
      ? 'border-amber-500 bg-amber-100 text-amber-900 ring-1 ring-amber-500'
      : 'border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-400',
    brand: active
      ? 'border-brand-600 bg-brand-100 text-brand-900 ring-1 ring-brand-600'
      : 'border-slate-200 bg-white text-slate-700 hover:border-brand-400',
    red: active
      ? 'border-red-600 bg-red-100 text-red-900 ring-1 ring-red-600'
      : 'border-red-200 bg-red-50 text-red-800 hover:border-red-400',
    slate: active
      ? 'border-slate-600 bg-slate-200 text-slate-900 ring-1 ring-slate-600'
      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400',
  }

  return (
    <button
      type="button"
      className={`rounded-full border px-3 py-1.5 transition duration-motion-micro ease-motion-standard ${toneClasses[tone]}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {count} {label}
    </button>
  )
}

function AlertTypeIcon({ alertType }) {
  if (alertType === 'overload') {
    return (
      <svg
        aria-hidden="true"
        className="h-3.5 w-3.5 text-red-600"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 19h16M6 16V9m6 7V5m6 11v-4" />
      </svg>
    )
  }

  return (
    <svg
      aria-hidden="true"
      className="h-3.5 w-3.5 text-amber-600"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l5-5 4 3 7-8" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 6h5v5" />
    </svg>
  )
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không xác định'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function directiveFiltersOverlap(leftAlertType, leftSeverity, rightAlertType, rightSeverity) {
  const typeOverlaps =
    leftAlertType === 'all' || rightAlertType === 'all' || leftAlertType === rightAlertType
  const severityOverlaps =
    leftSeverity === 'all' || rightSeverity === 'all' || leftSeverity === rightSeverity
  return typeOverlaps && severityOverlaps
}

function formatDepartmentDirectiveFilter(value) {
  const labels = {
    all: 'Tất cả',
    early_warning: 'Dấu hiệu sớm',
    overload: 'Quá tải',
    medium: 'Mức trung bình',
    high: 'Mức cao',
  }
  return labels[value] || 'Không xác định'
}

export default AlertsPage
