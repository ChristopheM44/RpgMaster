import { defineStore } from 'pinia'
import { ref } from 'vue'
import { campaignApi } from '../services/api'
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
      campaigns.value = await campaignApi.list()
    } catch (e) {
      error.value = 'Erreur de chargement des campagnes'
    } finally {
      loading.value = false
    }
  }

  async function createCampaign(body: CampaignCreate): Promise<Campaign | null> {
    try {
      const campaign = await campaignApi.create(body)
      campaigns.value.unshift(campaign)
      return campaign
    } catch {
      error.value = 'Erreur lors de la création de la campagne'
      return null
    }
  }

  async function fetchCampaign(id: string): Promise<Campaign | null> {
    try {
      const campaign = await campaignApi.get(id)
      currentCampaign.value = campaign
      return campaign
    } catch {
      return null
    }
  }

  async function fetchScenario(id: string): Promise<CampaignScenario | null> {
    try {
      const scenario = await campaignApi.getScenario(id)
      scenarios.value[id] = scenario
      return scenario
    } catch {
      error.value = 'Erreur de chargement du scénario'
      return null
    }
  }

  async function fetchGmDossier(id: string): Promise<CampaignGmDossierResponse | null> {
    try {
      const dossier = await campaignApi.getGmDossier(id)
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
      return await campaignApi.importSource(campaignId, body)
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
      return await campaignApi.forgeDraft(campaignId, brief, options)
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
      const data = await campaignApi.validateContract(campaignId, playerContract)
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
      const updated = await campaignApi.attachSession(campaignId, sessionId)
      currentCampaign.value = updated
      return updated
    } catch {
      error.value = "Erreur lors de l'attachement de session"
      return null
    }
  }

  async function advance(campaignId: string, newSessionName: string): Promise<CampaignAdvanceResponse | null> {
    try {
      const data = await campaignApi.advance(campaignId, {
        new_session_name: newSessionName,
      } as CampaignAdvanceBody)
      currentCampaign.value = data.campaign
      return data
    } catch {
      error.value = 'Erreur lors du passage à la session suivante'
      return null
    }
  }

  async function deleteCampaign(id: string) {
    await campaignApi.delete(id)
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
