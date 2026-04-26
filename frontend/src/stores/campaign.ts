import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  Campaign,
  CampaignCreate,
  CampaignAdvanceBody,
  CampaignAdvanceResponse,
  CampaignForgeDraftResponse,
  CampaignGmDossierResponse,
  CampaignImportSourceBody,
  CampaignImportSourceResponse,
  CampaignPlayerContract,
  CampaignScenario,
} from '../types'

const API = 'http://localhost:8000/api/campaigns'

export const useCampaignStore = defineStore('campaign', () => {
  const campaigns = ref<Campaign[]>([])
  const currentCampaign = ref<Campaign | null>(null)
  const scenarios = ref<Record<string, CampaignScenario>>({})
  const gmDossiers = ref<Record<string, CampaignGmDossierResponse>>({})
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

  async function fetchScenario(id: string): Promise<CampaignScenario | null> {
    try {
      const res = await fetch(`${API}/${id}/scenario`)
      if (!res.ok) throw new Error()
      const scenario: CampaignScenario = await res.json()
      scenarios.value[id] = scenario
      return scenario
    } catch {
      error.value = 'Erreur de chargement du scénario'
      return null
    }
  }

  async function fetchGmDossier(id: string): Promise<CampaignGmDossierResponse | null> {
    try {
      const res = await fetch(`${API}/${id}/gm-dossier`)
      if (!res.ok) throw new Error()
      const dossier: CampaignGmDossierResponse = await res.json()
      gmDossiers.value[id] = dossier
      return dossier
    } catch {
      error.value = 'Erreur de chargement des notes MJ'
      return null
    }
  }

  async function importSource(
    campaignId: string,
    body: CampaignImportSourceBody,
  ): Promise<CampaignImportSourceResponse | null> {
    try {
      const res = await fetch(`${API}/${campaignId}/import-source`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error()
      return await res.json()
    } catch {
      error.value = "Erreur lors de l'import de la source"
      return null
    }
  }

  async function forgeDraft(
    campaignId: string,
    brief: Record<string, unknown>,
    options: Record<string, unknown>,
  ): Promise<CampaignForgeDraftResponse | null> {
    try {
      const res = await fetch(`${API}/${campaignId}/forge-draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief, options }),
      })
      if (!res.ok) throw new Error()
      return await res.json()
    } catch {
      error.value = 'Erreur lors de la forge de campagne'
      return null
    }
  }

  async function validateContract(
    campaignId: string,
    playerContract: CampaignPlayerContract,
  ): Promise<CampaignForgeDraftResponse | null> {
    try {
      const res = await fetch(`${API}/${campaignId}/validate-contract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_contract: playerContract }),
      })
      if (!res.ok) throw new Error()
      const data: CampaignForgeDraftResponse = await res.json()
      const updated = await fetchCampaign(campaignId)
      if (updated) {
        const idx = campaigns.value.findIndex((c) => c.id === campaignId)
        if (idx !== -1) campaigns.value[idx] = updated
      }
      await fetchScenario(campaignId)
      return data
    } catch {
      error.value = 'Erreur lors de la validation du contrat'
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
    scenarios,
    gmDossiers,
    loading,
    error,
    fetchCampaigns,
    createCampaign,
    fetchCampaign,
    fetchScenario,
    fetchGmDossier,
    importSource,
    forgeDraft,
    validateContract,
    attachSession,
    advance,
    deleteCampaign,
  }
})
