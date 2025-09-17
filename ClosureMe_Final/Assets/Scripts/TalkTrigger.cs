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

    public AudioSource voiceSource; // 指到播放 TTS 的那顆 AudioSource
    public int talkingVariants = 2;                  // 你有幾種 Talking
    public Vector2Int talkLoopsPerVariant = new Vector2Int(1, 2); // 每支要播幾圈才換(隨機)
    public float postSwapCooldown = 0.12f;          // 換完的緩衝，避免抖動
    private Coroutine talkCycler;

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

        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);
        StartCoroutine(DriveTalkingByAudio());
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
        if (talkCycler != null) { StopCoroutine(talkCycler); talkCycler = null; }
    }

    IEnumerator DelayedLookAt(Vector3 targetPos)
    {
        yield return null;
        Vector3 dir = targetPos - transform.parent.position;
        dir.y = 0f;
        if (dir != Vector3.zero)
            transform.parent.rotation = Quaternion.LookRotation(dir);
    }

    private IEnumerator DriveTalkingByAudio()
    {
        // 等待 AudioSource 開始播放（設個超時計時，避免永遠等不到）
        float timeout = 10f, t = 0f;
        while (voiceSource && !voiceSource.isPlaying && t < timeout)
        {
            t += Time.deltaTime;
            yield return null;
        }

        // 若真的有開始播 → 切到 Talking
        if (voiceSource && voiceSource.isPlaying && aiAnimator)
        {
            aiAnimator.SetAIState(AIAnimationController.AIState.Talking);
            // 立刻給一個起始變體
            aiAnimator.SetTalkingVariant(Random.Range(0, talkingVariants));
            // 啟動輪播
            if (talkCycler != null) StopCoroutine(talkCycler);
            talkCycler = StartCoroutine(CycleTalkingVariants());
        }


        // 等到語音播完
        if (voiceSource)
            yield return new WaitWhile(() => voiceSource.isPlaying);

        // 播完回到 Thinking（或 Idle，看你的需求）
        if (aiAnimator) aiAnimator.SetAIState(AIAnimationController.AIState.Thinking);
    }
    private IEnumerator CycleTalkingVariants()
    {
        var anim = aiAnimator.GetComponent<Animator>();
        int last = -1;
        int loopsLeft = Random.Range(talkLoopsPerVariant.x, talkLoopsPerVariant.y + 1);

        float prevFrac = 0f;
        while (voiceSource && voiceSource.isPlaying)
        {
            yield return null;

            if (!voiceSource.isPlaying || anim == null) break;
            if (anim.IsInTransition(0)) continue;
            var st = anim.GetCurrentAnimatorStateInfo(0);
            bool inTalking = st.IsName("Talking_0") || st.IsName("Talking_1") || st.IsName("Talking_2");
            if (!inTalking) { prevFrac = 0f; continue; }

            float frac = st.normalizedTime % 1f;
            if (frac < prevFrac)
            {
                loopsLeft--;
                if (loopsLeft <= 0)
                {
                    int next = (talkingVariants <= 1) ? 0 : Random.Range(0, talkingVariants);
                    if (talkingVariants > 1 && next == last)
                        next = (next + 1) % talkingVariants;

                    aiAnimator.SetTalkingVariant(next);
                    last = next;
                    loopsLeft = Random.Range(talkLoopsPerVariant.x, talkLoopsPerVariant.y + 1);
                    if (postSwapCooldown > 0f)
                        yield return new WaitForSeconds(postSwapCooldown);
                }
            }

            prevFrac = frac;
        }
        talkCycler = null;
    }
}
