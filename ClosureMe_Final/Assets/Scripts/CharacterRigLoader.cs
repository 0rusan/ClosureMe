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


    }
}