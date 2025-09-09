using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;

public class MapManager : MonoBehaviour
{
    [Tooltip("指向你的 XROrigin 或玩家根物件")]
    public Transform playerRoot;

    [Tooltip("Spawn 的 Tag 名稱；預設使用 Spawn")]
    public string spawnTag = "Spawn";

    string loadedMapScene = null;

    public IEnumerator SwitchTo(string sceneName)
    {
        // 卸載舊地圖
        if (!string.IsNullOrEmpty(loadedMapScene))
        {
            var unload = SceneManager.UnloadSceneAsync(loadedMapScene);
            if (unload != null) yield return unload;
        }

        // 載入新地圖（Additive）
        var load = SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive);
        if (load == null)
        {
            Debug.LogError($"[MapManager] 無法載入場景：{sceneName}，請確認已加入 Build Settings。");
            yield break;
        }
        yield return load;
        loadedMapScene = sceneName;

        // 等一禎讓物件註冊完成
        yield return null;

        // 找 Spawn 並把玩家移過去
        var spawn = GameObject.FindWithTag(spawnTag);
        if (spawn != null && playerRoot != null)
        {
            playerRoot.position = spawn.transform.position;
            playerRoot.rotation = spawn.transform.rotation;
        }
        else
        {
            Debug.LogWarning($"[MapManager] 找不到 Tag={spawnTag} 的出生點或 playerRoot 未指定。");
        }
    }
}
