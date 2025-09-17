using UnityEngine;
using UnityEngine.AI; // 引用 AI 命名空間，NavMeshAgent 在這裡

// 確保物件身上有 NavMeshAgent 組件
[RequireComponent(typeof(NavMeshAgent))]
public class NpcWanderController : MonoBehaviour
{
    // 公開變數，可以在 Unity Inspector 中調整
    [Tooltip("NPC 搜尋新目標點的半徑")]
    public float wanderRadius = 10f;

    [Tooltip("NPC 到達目標後，停留多久再找下一個點 (秒)")]
    public float wanderTimer = 5f;
    private float speedThreshold = 0.15f;

    private NavMeshAgent agent;
    private float timer;
    private AIAnimationController aiAnimator;

    // 在腳本啟動時執行一次
    void OnEnable()
    {
        // 獲取物件身上的 NavMeshAgent 組件
        agent = GetComponent<NavMeshAgent>();
        // 初始化計時器
        timer = wanderTimer;
        aiAnimator = GetComponent<AIAnimationController>();

    }

    // 每幀都會執行
    void Update()
    {
        if (aiAnimator != null && aiAnimator.IsConversing())
            return; // 若在對話中，不要介入控制動畫

        // 計時器倒數
        timer += Time.deltaTime;
        // 如果計時器時間到，並且 NPC 已經接近當前目標點
        if (timer >= wanderTimer)
        {
            // 在指定半徑內尋找一個隨機的新目標點
            Vector3 newPos = RandomNavSphere(transform.position, wanderRadius, -1);
            // 命令 Agent 前往新目標點
            agent.SetDestination(newPos);
            // 重置計時器
            timer = 0;
        }

        if (aiAnimator)
        {
            if (agent.velocity.magnitude > speedThreshold)
                aiAnimator.SetAIState(AIAnimationController.AIState.Walk);
            else
                aiAnimator.SetAIState(AIAnimationController.AIState.Idle);
        }
    }

    /// <summary>
    /// 在一個球形範圍內，尋找 NavMesh 上的隨機一個點
    /// </summary>
    /// <param name="origin">搜尋的中心點</param>
    /// <param name="dist">搜尋的半徑</param>
    /// <param name="layermask">NavMesh 的圖層遮罩</param>
    /// <returns>NavMesh 上的有效位置</returns>
    public static Vector3 RandomNavSphere(Vector3 origin, float dist, int layermask)
    {
        // 在 origin 周圍的球體內產生一個隨機方向的點
        Vector3 randDirection = Random.insideUnitSphere * dist;
        randDirection += origin;

        NavMeshHit navHit;

        // 從隨機點尋找最近的 NavMesh 上的點
        // NavMesh.SamplePosition 會尋找最近的有效點，並將資訊儲存在 navHit 中
        NavMesh.SamplePosition(randDirection, out navHit, dist, layermask);

        return navHit.position;
    }
}