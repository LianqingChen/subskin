/**
 * VASI API Client
 * 
 * Handles all VASI assessment related API calls to backend.
 * Token is retrieved from localStorage.
 */

const API_BASE_URL = '/api'
const VASI_ENDPOINT = `${API_BASE_URL}/vasi`

/**
 * Get authentication token from localStorage
 * @returns {string|null} JWT token or null
 */
function getToken() {
  return localStorage.getItem('auth_token') || localStorage.getItem('token')
}

/**
 * Make authenticated API request
 * @param {string} url - API endpoint URL
 * @param {object} options - Fetch options
 * @returns {Promise<object>} Response data
 */
async function fetchAPI(url, options = {}) {
  const token = getToken()
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.detail || data.message || `API Error: ${response.status}`)
    }
    
    return data
  } catch (error) {
    if (error instanceof Error) {
      throw error
    }
    throw new Error('Network error: Failed to connect to server')
  }
}

/**
 * Create a new VASI assessment
 * @param {File} image - Image file to upload
 * @param {string} bodySite - Body site (face, neck, trunk, upper_limb, lower_limb, other)
 * @returns {Promise<object>} Assessment result with VASI score
 */
export async function createAssessment(image, bodySite) {
  const token = getToken()
  
  if (!token) {
    throw new Error('请先登录')
  }
  
  const formData = new FormData()
  formData.append('image', image)
  formData.append('body_site', bodySite)
  
  try {
    const response = await fetch(`${VASI_ENDPOINT}/assess`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new Error(data.detail || data.message || '评估失败，请稍后重试')
    }
    
    return data
  } catch (error) {
    if (error instanceof Error) {
      throw error
    }
    throw new Error('网络错误：无法连接到服务器')
  }
}

/**
 * Get assessment history
 * @param {object} params - Query parameters
 * @param {string} [params.body_site] - Filter by body site
 * @param {number} [params.page=1] - Page number
 * @param {number} [params.page_size=20] - Items per page
 * @returns {Promise<object>} History data with assessments array
 */
export async function getHistory(params = {}) {
  const queryParams = new URLSearchParams({
    page: params.page || 1,
    page_size: params.page_size || 20,
    ...(params.body_site && { body_site: params.body_site }),
  })
  
  return fetchAPI(`${VASI_ENDPOINT}/history?${queryParams}`)
}

/**
 * Get single assessment details
 * @param {string|number} assessmentId - Assessment ID
 * @returns {Promise<object>} Assessment details
 */
export async function getAssessment(assessmentId) {
  return fetchAPI(`${VASI_ENDPOINT}/assess/${assessmentId}`)
}

/**
 * Get trend data for chart visualization
 * @param {object} params - Query parameters
 * @param {number} [params.days=30] - Time range in days
 * @param {string} [params.body_site] - Filter by body site
 * @returns {Promise<object>} Trend data with score history
 */
export async function getTrend(params = {}) {
  const queryParams = new URLSearchParams({
    days: params.days || 30,
    ...(params.body_site && { body_site: params.body_site }),
  })
  
  return fetchAPI(`${VASI_ENDPOINT}/trend?${queryParams}`)
}

/**
 * Body site configuration
 */
export const BODY_SITES = {
  face: { label: '面部', icon: '😊' },
  neck: { label: '颈部', icon: '🦒' },
  trunk: { label: '躯干', icon: '👕' },
  upper_limb: { label: '上肢', icon: '💪' },
  lower_limb: { label: '下肢', icon: '🦵' },
  other: { label: '其他', icon: '📷' },
}

/**
 * Disease stage configuration
 */
export const DISEASE_STAGES = {
  improving: { label: '好转', color: '#2f855a', icon: '✅' },
  stable: { label: '稳定', color: '#d69e2e', icon: '⏸️' },
  spreading: { label: '扩散', color: '#e53e3e', icon: '⚠️' },
}

/**
 * Disease type configuration
 */
export const DISEASE_TYPES = {
  segmental: { label: '节段型', description: '局限于一个皮节区域' },
  non_segmental: { label: '非节段型', description: '对称或广泛分布' },
  mixed: { label: '混合型', description: '同时具备节段型和非节段型特征' },
}

/**
 * Time range options for trend chart
 */
export const TIME_RANGES = [
  { value: 7, label: '7天' },
  { value: 30, label: '30天' },
  { value: 90, label: '90天' },
  { value: 180, label: '180天' },
  { value: 365, label: '365天' },
]
