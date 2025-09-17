using UnityEngine;

public class ModelSwitcher : MonoBehaviour
{
    public CharacterRigLoader rigLoader;

    void Start()
    {
        Switch("AIAgentModel");  // 固定名字
    }

    public void Switch(string prefabName)
    {
        var go = Resources.Load<GameObject>($"Agents/{prefabName}");
        if (go == null)
        {
            Debug.LogError($"找不到 Prefab：Agents/{prefabName}");
            return;
        }
        rigLoader.SetModel(go);
    }
}
