import { ref } from 'vue'

/** BubbleMenu 与闪闪面板共享的指令草稿 */
const agentDraft = ref('')

export function useAgentDraft() {
  function clearAgentDraft() {
    agentDraft.value = ''
  }

  return { agentDraft, clearAgentDraft }
}
