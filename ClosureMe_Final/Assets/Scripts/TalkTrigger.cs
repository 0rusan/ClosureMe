using UnityEngine.AI;
using UnityEngine;
using TMPro;
using System.Collections;

public class TalkTrigger : MonoBehaviour
{
    public DialogueUI dialogueUI;
    public AIResponseManager aiManager;
    public TMP_InputField inputField;
    public AIAnimationController aiAnimator;
    public STTAPI sttAPI;

    private bool playerInRange = false;
    private bool isAwaiting = false;
    private NavMeshAgent agent;
    private Transform playerTransform;

    void Start()
    {
        agent = GetComponentInParent<NavMeshAgent>();

        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        inputField.gameObject.SetActive(false);
        inputField.onEndEdit.RemoveAllListeners();
        inputField.onEndEdit.AddListener(OnInputSubmit);
    }

    void Update()
    {
        if (!playerInRange) return;

        // === PC 鍵盤 ===
        if (Input.GetKeyDown(KeyCode.E))
            VR_Interact();                 // 與 VR 走同一條路

        if (Input.GetKeyDown(KeyCode.R))
            VR_RecordStart();              // 與 VR 走同一條路

        if (Input.GetKeyDown(KeyCode.T))
            VR_RecordStop();               // 與 VR 走同一條路

        if (Input.GetKeyDown(KeyCode.Escape))
            VR_Cancel();

        // 對話結束 → 讓 NavMeshAgent 繼續走
        if (!isAwaiting && !dialogueUI.IsDialogueActive() && agent && agent.isStopped)
        {
            agent.isStopped = false;
            if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Walk);
        }
    }

    void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            playerInRange = true;
            playerTransform = other.transform;
        }
    }

    void OnTriggerExit(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            playerInRange = false;
            EndDialogue();
        }
    }

    // ====== 供 PC/VR 共用的公開方法 ======

    // E：開始打字對話
    public void VR_Interact()
    {
        if (!playerInRange || dialogueUI.IsDialogueActive() || isAwaiting || sttAPI.IsRecording) return;

        isAwaiting = true;
        if (agent) agent.isStopped = true;
        if (playerTransform) StartCoroutine(DelayedLookAt(playerTransform.position));
        dialogueUI.StartDialogue(new System.Collections.Generic.List<string> { "..." });
        aiManager.AskAI("~INIT~");

        inputField.gameObject.SetActive(true);
        inputField.ActivateInputField();

        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);
    }

    // R：開始錄音（長按/按下）
    public void VR_RecordStart(int maxSeconds = 30)
    {
        if (!playerInRange || isAwaiting || sttAPI.IsRecording) return;

        isAwaiting = true;
        if (agent) agent.isStopped = true;
        if (playerTransform) StartCoroutine(DelayedLookAt(playerTransform.position));
        dialogueUI.StartDialogue(new System.Collections.Generic.List<string> { "（開始錄音…放開結束）" });
        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);

        sttAPI.BeginRecording(maxSeconds);
    }

    // T：結束錄音（或 A 鍵放開）
    public void VR_RecordStop()
    {
        if (!playerInRange || !sttAPI.IsRecording) return;

        StartCoroutine(sttAPI.StopAndTranscribe(txt =>
        {
            if (string.IsNullOrWhiteSpace(txt))
            {
                dialogueUI.StartDialogue(new System.Collections.Generic.List<string> { "（我沒聽清楚，再說一次？）" });
                OnAIResponseFinished();
                return;
            }
            aiManager.AskAI(txt);
        }));
    }

    // Esc / B：離開或中止
    public void VR_Cancel()
    {
        if (!playerInRange) return;
        EndDialogue();
    }

    // ====== 其餘維持原狀 ======

    public void OnInputSubmit(string msg)
    {
        if (string.IsNullOrWhiteSpace(msg) || isAwaiting || !playerInRange) return;

        isAwaiting = true;
        aiManager.AskAI(msg);

        inputField.text = "";
        inputField.DeactivateInputField();
        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);
    }

    public void OnAIResponseFinished()
    {
        isAwaiting = false;
        inputField.ActivateInputField();
        if (aiAnimator)
        {
            aiAnimator.SetAIState(AIAnimationController.AIState.Talking);
            StartCoroutine(SwitchToThinkingAfterDelay(3.933f));
        }
    }

    private void EndDialogue()
    {
        dialogueUI.EndDialogue();
        isAwaiting = false;
        if (agent) agent.isStopped = false;

        inputField.text = "";
        inputField.DeactivateInputField();
        inputField.gameObject.SetActive(false);

        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Idle);
    }

    IEnumerator DelayedLookAt(Vector3 targetPos)
    {
        yield return null;
        Vector3 dir = targetPos - transform.parent.position;
        dir.y = 0f;
        if (dir != Vector3.zero)
            transform.parent.rotation = Quaternion.LookRotation(dir);
    }

    IEnumerator SwitchToThinkingAfterDelay(float delay)
    {
        yield return new WaitForSeconds(delay);
        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);
    }
}
