#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;
using System.IO;

public static class HttpModelFetcher
{
    private const string MODEL_URL = "http://122.100.76.28:80/models/AIAgentModel.fbx";
    private const string INCOMING_DIR = "Assets/AgentModels/Incoming";
    private static readonly string DEST_FBX = Path.Combine(INCOMING_DIR, "AIAgentModel.fbx").Replace('\\', '/');
    [MenuItem("Tools/Agents/Fetch Latest Model (HTTP) %#F")]
    public static void FetchMenu() => DownloadAndImport(null);

    static bool _fetchInProgress = false, _resumePending = false;

    [InitializeOnLoadMethod]
    private static void AutoFetchOnPlayEnter()
    {
        EditorApplication.playModeStateChanged += s =>
        {
            if (s != PlayModeStateChange.ExitingEditMode) return;
            if (_resumePending) { _resumePending = false; return; }
            if (!EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isPlaying) return;
            if (_fetchInProgress) return;

            _fetchInProgress = true;
            EditorApplication.isPlaying = false;

            Debug.Log("[HttpModelFetcher] ⏳ Fetch before Play...");
            DownloadAndImport(() =>
            {
                AssetDatabase.Refresh();                         // 確保資產出現在 DB
                EditorUtility.UnloadUnusedAssetsImmediate(true);  // 卸掉舊引用（避免無 Domain Reload 時殘留）
                _fetchInProgress = false;
                _resumePending = true;

                EditorApplication.delayCall += () =>
                {
                    Debug.Log("[HttpModelFetcher] Fetch done, entering Play.");
                    EditorApplication.isPlaying = true;
                };
            });
        };
    }

    private static UnityWebRequest req;
    private static System.Action onComplete;

    private static void DownloadAndImport(System.Action onDone)
    {
        onComplete = onDone;
        // 加上破快取參數與標頭
        var url = MODEL_URL + "?t=" + System.DateTime.UtcNow.Ticks;
        req = UnityWebRequest.Get(url);
        req.SetRequestHeader("Cache-Control", "no-cache");
        req.SetRequestHeader("Pragma", "no-cache");
        req.SendWebRequest();
        EditorApplication.update += UpdateLoop;
    }

    private static void UpdateLoop()
    {
        if (req == null || !req.isDone) return;
        EditorApplication.update -= UpdateLoop;

        if (req.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError($"[HttpModelFetcher] 下載失敗：{req.error}");
        }
        else
        {
            var bytes = req.downloadHandler.data ?? System.Array.Empty<byte>();
            // 方便你確認是否真的換檔
            string md5 = System.BitConverter.ToString(
                System.Security.Cryptography.MD5.Create().ComputeHash(bytes)).Replace("-", "");
            Debug.Log($"[HttpModelFetcher] bytes={bytes.Length}, md5={md5}");

            Directory.CreateDirectory(INCOMING_DIR);
            File.WriteAllBytes(DEST_FBX, bytes);
            Debug.Log($"[HttpModelFetcher] 已更新：{DEST_FBX}");

            // 強制 Reimport（模型有子資產）
            AssetDatabase.ImportAsset(DEST_FBX, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ImportRecursive);
            AssetDatabase.SaveAssets();
        }

        req.Dispose(); req = null;
        onComplete?.Invoke(); onComplete = null;
    }
}
#endif