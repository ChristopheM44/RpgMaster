import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Campaign, CampaignCreate, CampaignAdvanceBody, CampaignAdvanceResponse } from '../types'

const API = 'http://localhost:8000/api/campaigns'

export const useCampaignStore = defineStore('campaign', () => {
  const campaigns = ref<Campaign[]>([])
  const currentCampaign = ref<Campaign | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCampaigns() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(API)
      campaigns.value = await res.json()
    } catch (e) {
      error.value = 'Erreur de chargement des campagnes'
    } finally {
      loading.value = false
    }
  }

  async function createCampaign(body: CampaignCreate): Promise<Campaign | null> {
    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('Création échouée')
      const campaign: Campaign = await res.json()
      campaigns.value.unshift(campaign)
      return campaign
    } catch {
      error.value = 'Erreur lors de la création de la campagne'
      return null
    }
  }

  async function fetchCampaign(id: string): Promise<Campaign | null> {
    try {
      const res = await fetch(`${API}/${id}`)
      if (!res.ok) return null
      const campaign: Campaign = await res.json()
      currentCampaign.value = campaign
      return campaign
    } catch {
      return null
    }
  }

  async function attachSession(campaignId: string, sessionId: string): Promise<Campaign | null> {
    try {
      const res = await fetch(`${API}/${campaignId}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      if (!res.ok) throw new Error()
      const updated: Campaign = await res.json()
      currentCampaign.value = updated
      return updated
    } catch {
      error.value = "Erreur lors de l'attachement de session"
      return null
    }
  }

  async function advance(campaignId: string, newSessionName: string): Promise<CampaignAdvanceResponse | null> {
    try {
      const res = await fetch(`${API}/${campaignId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_session_name: newSessionName } as CampaignAdvanceBody),
      })
      if (!res.ok) throw new Error()
      const data: CampaignAdvanceResponse = await res.json()
      currentCampaign.value = data.campaign
      return data
    } catch {
      error.value = 'Erreur lors du passage à la session suivante'
      return null
    }
  }

  async function deleteCampaign(id: string) {
    await fetch(`${API}/${id}`, { method: 'DELETE' })
    campaigns.value = campaigns.value.filter((c) => c.id !== id)
    if (currentCampaign.value?.id === id) currentCampaign.value = null
  }

  return {
    campaigns,
    currentCampaign,
    loading,
    error,
    fetchCampaigns,
    createCampaign,
    fetchCampaign,
    attachSession,
    advance,
    deleteCampaign,
  }
})
