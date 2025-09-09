///第一版///
using UnityEditor;
using UnityEngine;

public class CharacterRigLoader : MonoBehaviour
{
    [Header("指向可替換的模型 Prefab（Humanoid）")]
    public GameObject modelPrefab;
    [Header("容器")]
    public Transform modelAnchor;
    private Animator rootAnimator;
    private GameObject modelInstance;

    void Awake()
    {
        rootAnimator = GetComponent<Animator>();
        if (modelAnchor == null)
        {
            var go = new GameObject("ModelAnchor");
            modelAnchor = go.transform;
            modelAnchor.SetParent(transform, false);   // 等同於 modelAnchor.parent = transform; 並保持當前局部座標
            modelAnchor.localPosition = Vector3.zero;
            modelAnchor.localRotation = Quaternion.identity;
            modelAnchor.localScale = Vector3.one;
        }
    }

    void Start()
    {
        if (modelPrefab) SetModel(modelPrefab);
    }

    public void SetModel(GameObject prefab)
    {
        if (modelInstance) Destroy(modelInstance);

        modelInstance = Instantiate(prefab, modelAnchor);
        modelInstance.transform.localPosition = Vector3.zero;
        modelInstance.transform.localRotation = Quaternion.identity;
        modelInstance.transform.localScale = Vector3.one;

        // 取得模型上的 Animator（只拿 Avatar），避免雙 Animator 搶控制
        var modelAnimator = modelInstance.GetComponentInChildren<Animator>();
        if (!modelAnimator || !modelAnimator.avatar || !modelAnimator.avatar.isHuman)
        {
            Debug.LogError("❌ 模型沒有 Humanoid Avatar，請在 Import 設成 Humanoid。");
            return;
        }

        // 把 Avatar 綁到 Root 的 Animator；Root 使用共用的 RuntimeAnimatorController
        rootAnimator.avatar = modelAnimator.avatar;

        // 可選：移除模型上的 Animator，避免重複驅動
        modelAnimator.runtimeAnimatorController = null;
        modelAnimator.enabled = false;

        // 自動適配碰撞體高度
        FitCapsuleToAvatar(rootAnimator);

    }

    private void FitCapsuleToAvatar(Animator anim)
    {
        var cap = GetComponent<CapsuleCollider>();
        if (!cap) return;

        // 用 Avatar 的身高估算：頭頂與腳底高度
        Vector3 hip; if (anim.GetBoneTransform(HumanBodyBones.Hips) != null)
            hip = anim.GetBoneTransform(HumanBodyBones.Hips).position;
        var head = anim.GetBoneTransform(HumanBodyBones.Head);
        var foot = anim.GetBoneTransform(HumanBodyBones.LeftFoot) ?? anim.GetBoneTransform(HumanBodyBones.RightFoot);

        if (head && foot)
        {
            float height = Mathf.Max(1.4f, Vector3.Distance(head.position, foot.position) + 0.2f);
            cap.height = height;
            cap.center = new Vector3(0, height * 0.5f, 0);
            cap.radius = Mathf.Clamp(height * 0.2f, 0.2f, 0.5f);
        }
    }
}
///第二版///
/*using UnityEngine;

public class CharacterRigLoader : MonoBehaviour
{
    [Header("Humanoid 模型 Prefab")]
    public GameObject modelPrefab;

    [Header("掛點（未指定自建 ModelAnchor）")]
    public Transform modelAnchor;

    [Header("VR 可見性 / 高度")]
    public string forceLayerName = "Default";   // 角色強制進這層（相機要勾）
    public bool adjustHeight = true;            // 出生高度：射線往下貼地
    public LayerMask groundLayers = ~0;
    // 內部
    Animator rootAnimator;     // 掛在本物件上的（舊邏輯可能會對它 SetBool）
    GameObject modelInstance;
    Animator modelAnimator;

    void Awake()
    {
        rootAnimator = GetComponent<Animator>();
        if (!modelAnchor)
        {
            var go = new GameObject("ModelAnchor");
            modelAnchor = go.transform;
            modelAnchor.SetParent(transform, false);
        }
    }

    void Start()
    {
        if (modelPrefab) SetModel(modelPrefab);
    }

    public void SetModel(GameObject prefab)
    {
        if (!prefab) return;
        if (modelInstance) Destroy(modelInstance);

        // 生成
        modelInstance = Instantiate(prefab, modelAnchor);
        modelInstance.name = prefab.name;
        modelInstance.transform.localPosition = Vector3.zero;
        modelInstance.transform.localRotation = Quaternion.identity;
        modelInstance.transform.localScale = Vector3.one;

        // Animator：由模型驅動；根 Animator 只當參數入口（避免警告）
        modelAnimator = modelInstance.GetComponentInChildren<Animator>(true);
        if (!modelAnimator || modelAnimator.avatar == null || !modelAnimator.avatar.isHuman)
        {
            Debug.LogError("[RigLoader] 模型需為 Humanoid，且 Avatar 有效。");
            return;
        }

        var ctrl = rootAnimator ? rootAnimator.runtimeAnimatorController : null;
        if (ctrl && !modelAnimator.runtimeAnimatorController)
            modelAnimator.runtimeAnimatorController = ctrl;

        modelAnimator.applyRootMotion = false;
        modelAnimator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

        if (rootAnimator)
        {
            rootAnimator.avatar = null; // 不驅動骨架
            if (!rootAnimator.runtimeAnimatorController && ctrl)
                rootAnimator.runtimeAnimatorController = ctrl;
            rootAnimator.applyRootMotion = false;
            rootAnimator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
        }

        // 強制 Layer（跨專案打包最常見問題）
        if (!string.IsNullOrEmpty(forceLayerName))
        {
            int L = LayerMask.NameToLayer(forceLayerName);
            if (L >= 0) SetLayerRecursively(modelInstance, L);
        }

        // 1) 材質開 instancing（Single Pass Instanced 較不會掉一眼）
        foreach (var r in modelInstance.GetComponentsInChildren<Renderer>(true))
        {
            var mats = r.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
                if (mats[i] && !mats[i].enableInstancing) mats[i].enableInstancing = true;
            // 不碰 r.allowOcclusionWhenDynamic，維持你的舊流程預設
        }

        // 2) 只動 bounds（重點）：中心放在 Hips，尺寸放大（再視情況收斂）
        var hips = modelAnimator.GetBoneTransform(HumanBodyBones.Hips);
        var smr = modelInstance.GetComponentInChildren<SkinnedMeshRenderer>(true);
        var b = smr.localBounds;
        b.extents = new Vector3(0.6536233f, 1.241909f, 0.4885602f); // ← 你的三個數（半尺寸）
        smr.localBounds = b;
    }

    void LateUpdate()
    {
        // 極簡參數鏡射（維持舊腳本對 rootAnimator 設參數的相容性）
        if (!rootAnimator || !modelAnimator ||
            !rootAnimator.runtimeAnimatorController || !modelAnimator.runtimeAnimatorController) return;

        foreach (var p in rootAnimator.parameters)
        {
            switch (p.type)
            {
                case AnimatorControllerParameterType.Bool: modelAnimator.SetBool(p.nameHash, rootAnimator.GetBool(p.nameHash)); break;
                case AnimatorControllerParameterType.Int: modelAnimator.SetInteger(p.nameHash, rootAnimator.GetInteger(p.nameHash)); break;
                case AnimatorControllerParameterType.Float: modelAnimator.SetFloat(p.nameHash, rootAnimator.GetFloat(p.nameHash)); break;
                    // Trigger 如需支援，請改成用對應 Bool/事件；這裡刻意省略以維持簡潔。
            }
        }
    }

    // --- helpers ---
    static void SetLayerRecursively(GameObject go, int layer)
    {
        go.layer = layer;
        foreach (Transform c in go.transform) SetLayerRecursively(c.gameObject, layer);
    }
}
*/