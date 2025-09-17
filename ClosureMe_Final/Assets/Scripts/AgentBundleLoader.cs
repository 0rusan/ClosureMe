/*using UnityEngine;
using System.Collections;

public class AgentBundleLoader : MonoBehaviour
{
    [Header("Bundle URL (可用 file:// 或 http://)")]
    public string bundleUrl = "http://192.168.1.102/models/agent_current";

    [Header("Rig Loader 指向角色本體")]
    public CharacterRigLoader rigLoader;

    IEnumerator Start()
    {
        Debug.Log("[AgentBundleLoader] 下載 AssetBundle: " + bundleUrl);

        var www = UnityEngine.Networking.UnityWebRequestAssetBundle.GetAssetBundle(bundleUrl);
        yield return www.SendWebRequest();

        if (www.result != UnityEngine.Networking.UnityWebRequest.Result.Success)
        {
            Debug.LogError("[AgentBundleLoader] 載入失敗: " + www.error);
            yield break;
        }

        var bundle = UnityEngine.Networking.DownloadHandlerAssetBundle.GetContent(www);
        Debug.Log("[AgentBundleLoader] Bundle 載入成功");

        // 取第一個資產（就是你打包進去的 prefab）
        var names = bundle.GetAllAssetNames();
        if (names.Length == 0)
        {
            Debug.LogError("❌ 這個 bundle 沒有資產！");
            yield break;
        }

        Debug.Log("[AgentBundleLoader] 包含資產: " + names[0]);
        var prefab = bundle.LoadAsset<GameObject>(names[0]);

        // 丟給 RigLoader
        if (rigLoader)
        {
            rigLoader.SetModel(prefab);
            Debug.Log("[AgentBundleLoader] 已套用到 RigLoader");
        }
        else
        {
            Instantiate(prefab);
            Debug.Log("[AgentBundleLoader] 沒有 RigLoader，直接生成");
        }
    }
}
*/
/*
using UnityEngine;
using System.Collections;
using UnityEngine.Networking;

public class AgentBundleLoader : MonoBehaviour
{
    [Header("Bundle URL (file:// 或 http://)")]
    public string bundleUrl = "http://192.168.1.102/models/agent_current";

    [Header("Rig Loader 指向角色本體")]
    public CharacterRigLoader rigLoader;

    [Header("（可選）FBX/Prefab 名稱提示（不含副檔名）")]
    public string modelNameHint = "AIAgentModel";

    [Header("把角色放到這個容器底下（強烈建議）")]
    public Transform spawnParent;   // ← 指到場景中的 CharactersRoot

    [Header("除錯選項")]
    public bool placeInFrontOfCamera = false; // 正式上線請關閉

    IEnumerator Start()
    {
        // 先把自己移出任何 Camera/Head/XR Origin 層級，避免跟視角飄
        DetachFromCameraHierarchy();

        // 若指定了 SpawnParent，先把自己搬到那底下（保留世界座標）
        if (spawnParent) transform.SetParent(spawnParent, true);

        Debug.Log("[AgentBundleLoader] 下載 AssetBundle: " + bundleUrl);

        using var www = UnityWebRequestAssetBundle.GetAssetBundle(bundleUrl);
        yield return www.SendWebRequest();
        if (www.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError("[AgentBundleLoader] 載入失敗: " + www.error);
            yield break;
        }

        var bundle = DownloadHandlerAssetBundle.GetContent(www);
        Debug.Log("[AgentBundleLoader] Bundle 載入成功");

        // 資產清單（方便除錯）
        var names = bundle.GetAllAssetNames();
        Debug.Log($"[AgentBundleLoader] 資產數={names.Length}");
        for (int i = 0; i < names.Length; i++) Debug.Log($"  #{i}: {names[i]}");

        // 1) 先用名稱提示載入
        GameObject prefab = null;
        if (!string.IsNullOrEmpty(modelNameHint))
        {
            prefab = bundle.LoadAsset<GameObject>(modelNameHint);
            Debug.Log("[AgentBundleLoader] 以名稱載入: " + modelNameHint + " => " + (prefab ? "OK" : "NULL"));
        }

        // 2) 取不到就遍歷挑 Animator+SMR 的
        if (!prefab)
        {
            var all = bundle.LoadAllAssets<GameObject>();
            int best = -1;
            foreach (var go in all)
            {
                if (!go) continue;
                int score = 0;
                if (go.GetComponentInChildren<Animator>()) score += 10;
                if (go.GetComponentsInChildren<SkinnedMeshRenderer>(true).Length > 0) score += 5;
                if (go.name.ToLower().Contains("agent") || go.name.ToLower().Contains("model")) score += 2;
                if (score > best) { best = score; prefab = go; }
                Debug.Log($"[AgentBundleLoader] 候選：{go.name} (score={score})");
            }
        }

        if (!prefab)
        {
            Debug.LogError("❌ 此 bundle 內沒有可用的 Model Prefab。");
            yield break;
        }

        Debug.Log("[AgentBundleLoader] 選用 Prefab: " + prefab.name);

        // 套到 RigLoader（你專案是共用 Root Animator 的設計）
        if (rigLoader) { rigLoader.SetModel(prefab); Debug.Log("[AgentBundleLoader] 已套用到 RigLoader"); }
        else { Instantiate(prefab, spawnParent ? spawnParent : null); Debug.Log("[AgentBundleLoader] 沒有 RigLoader，直接生成"); }

        // 再次保險：確保當前角色在 SpawnParent 底下
        if (spawnParent) transform.SetParent(spawnParent, true);

        // 除錯：需要時才把角色搬到相機前
        if (placeInFrontOfCamera && Camera.main)
        {
            var cam = Camera.main.transform;
            transform.position = cam.position + cam.forward * 2f;
            transform.rotation = Quaternion.LookRotation(cam.forward, Vector3.up);
            Debug.Log("[AgentBundleLoader] Debug: 目標已移到相機前 2m");
        }
    }

    void DetachFromCameraHierarchy()
    {
        for (var t = transform.parent; t != null; t = t.parent)
        {
            var n = t.name.ToLower();
            if (n.Contains("camera") || n.Contains("head") || n.Contains("xr origin"))
            {
                Debug.LogWarning($"[AgentBundleLoader] 角色位於 {t.name} 之下，已自動脫離以避免跟視線飄。");
                transform.SetParent(null, true); // 脫離父節點，保留世界座標
                return;
            }
        }
    }
}
*/
using System;
using System.Collections;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Networking;

public class AgentBundleLoader : MonoBehaviour
{
    [Header("manifest.json URL 或 file:// 路徑")]
    public string manifestUrl = "http://192.168.1.102/models/manifest.json";

    [Header("Rig Loader（掛在你的角色根物件上）")]
    public CharacterRigLoader rigLoader;

    [Header("選擇性：把角色放到這個容器底下")]
    public Transform spawnParent;

    [Header("除錯")]
    public bool placeInFrontOfCamera = false;

    // 快取
    private string CacheDir => Path.Combine(Application.persistentDataPath, "AgentCache");
    private string BundlePath => Path.Combine(CacheDir, "agent.bundle");
    private const string PrefKey_MD5 = "AgentBundle_MD5";
    private AssetBundle _loadedBundle;

    [Serializable]
    private class RemoteManifest
    {
        public string version;
        public string prefabName;
        public string bundleUrl;
        public string md5;
    }

    IEnumerator Start()
    {
        DetachFromCameraHierarchy();
        if (spawnParent) transform.SetParent(spawnParent, true);
        Directory.CreateDirectory(CacheDir);

        // 1) 下載 & 解析 manifest（容錯）
        RemoteManifest manifest = null;
        string raw = null;
        using (var req = UnityWebRequest.Get(manifestUrl + "?t=" + DateTime.UtcNow.Ticks))
        {
            req.SetRequestHeader("Cache-Control", "no-cache");
            req.SetRequestHeader("Pragma", "no-cache");
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("[AgentBundleLoader] 讀 manifest 失敗: " + req.error);
                yield break;
            }
            raw = req.downloadHandler.text ?? "";
        }

        var preview = raw.Length > 200 ? raw.Substring(0, 200) : raw;
        // 去 BOM/零寬字元
        var text = raw.Replace("\uFEFF", "").Replace("\u200B", "").Replace("\u200C", "").Replace("\u200D", "").Trim();

        if (text.StartsWith("{"))
        {
            try { manifest = JsonUtility.FromJson<RemoteManifest>(text); }
            catch (Exception e)
            {
                Debug.LogError("[AgentBundleLoader] manifest 解析錯誤: " + e.Message + "\npreview=\n" + preview);
                yield break;
            }
        }
        else
        {
            var lower = text.ToLowerInvariant();
            bool looksUnityManifest = lower.Contains("manifestfileversion") || lower.Contains("assetbundlemanifest");
            bool urlIsUnityManifest = manifestUrl.ToLowerInvariant().EndsWith(".manifest");

            if (looksUnityManifest || urlIsUnityManifest)
            {
                var bundleUrl = urlIsUnityManifest
                    ? manifestUrl.Substring(0, manifestUrl.Length - ".manifest".Length)
                    : new Uri(new Uri(manifestUrl), "agent_current").ToString();

                manifest = new RemoteManifest
                {
                    version = DateTime.UtcNow.ToString("yyyyMMddHHmmss"),
                    prefabName = "AIAgentModel",
                    bundleUrl = bundleUrl,
                    md5 = "" // 非 JSON 無法驗 MD5
                };
                Debug.LogWarning("[AgentBundleLoader] 給到 Unity .manifest；已自動推斷 bundleUrl: " + bundleUrl);
            }
            else if (text.StartsWith("<"))
            {
                Debug.LogError("[AgentBundleLoader] 讀到 HTML（多半 404/目錄頁）。請把 manifestUrl 指向 manifest.json。\npreview=\n" + preview);
                yield break;
            }
            else
            {
                Debug.LogError("[AgentBundleLoader] 非 JSON；請確認 URL/內容/編碼。\npreview=\n" + preview);
                yield break;
            }
        }

        if (string.IsNullOrEmpty(manifest.bundleUrl) || manifest.bundleUrl.StartsWith("<"))
        {
            var baseUri = new Uri(manifestUrl);
            manifest.bundleUrl = new Uri(baseUri, "agent_current").ToString();
            Debug.LogWarning("[AgentBundleLoader] bundleUrl 未填；已自動推斷為: " + manifest.bundleUrl);
        }
        if (string.IsNullOrEmpty(manifest.prefabName)) manifest.prefabName = "AIAgentModel";

        // 2) 比對 MD5（有變才下載）
        bool needDownload = true;
        var localMD5 = PlayerPrefs.GetString(PrefKey_MD5, "");
        if (File.Exists(BundlePath) && !string.IsNullOrEmpty(localMD5) &&
            string.Equals(localMD5, manifest.md5, StringComparison.OrdinalIgnoreCase))
            needDownload = false;

        if (needDownload)
        {
            using var dl = UnityWebRequest.Get(manifest.bundleUrl + "?t=" + DateTime.UtcNow.Ticks);
            yield return dl.SendWebRequest();
            if (dl.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("[AgentBundleLoader] 下載 bundle 失敗: " + dl.error);
                yield break;
            }
            try { File.WriteAllBytes(BundlePath, dl.downloadHandler.data); }
            catch (Exception e) { Debug.LogError("[AgentBundleLoader] 寫入快取失敗: " + e); yield break; }

            if (!string.IsNullOrEmpty(manifest.md5) && !VerifyMD5(BundlePath, manifest.md5))
            {
                Debug.LogError("[AgentBundleLoader] MD5 驗證失敗，放棄載入。");
                yield break;
            }
            PlayerPrefs.SetString(PrefKey_MD5, manifest.md5 ?? "");
            PlayerPrefs.Save();
            Debug.Log("[AgentBundleLoader] ✅ 已更新快取：" + BundlePath);
        }
        else
        {
            Debug.Log("[AgentBundleLoader] 使用本地快取：" + BundlePath);
        }

        // 3) 由檔案載入 Bundle
        if (_loadedBundle != null) { _loadedBundle.Unload(false); _loadedBundle = null; }
        var reqAb = AssetBundle.LoadFromFileAsync(BundlePath);
        yield return reqAb;
        _loadedBundle = reqAb.assetBundle;
        if (_loadedBundle == null)
        {
            Debug.LogError("[AgentBundleLoader] AssetBundle 載入失敗（平台不一致或檔案損壞）。");
            yield break;
        }

        // 4) 取 Prefab
        GameObject prefab = _loadedBundle.LoadAsset<GameObject>(manifest.prefabName);
        if (!prefab)
        {
            var all = _loadedBundle.LoadAllAssets<GameObject>();
            int best = -1;
            foreach (var go in all)
            {
                if (!go) continue;
                int score = 0;
                if (go.GetComponentInChildren<Animator>()) score += 10;
                if (go.GetComponentsInChildren<SkinnedMeshRenderer>(true).Length > 0) score += 5;
                if (go.name.ToLower().Contains("agent") || go.name.ToLower().Contains("model")) score += 2;
                if (score > best) { best = score; prefab = go; }
            }
        }
        if (!prefab) { Debug.LogError("[AgentBundleLoader] 此 bundle 內沒有可用的 Prefab"); yield break; }

        // 5) 套進 RigLoader（建議你已用 VR 穩定版 CharacterRigLoader）
        if (rigLoader) { rigLoader.SetModel(prefab); Debug.Log("[AgentBundleLoader] ✅ 已套用到 RigLoader: " + prefab.name); }
        else
        {
            var inst = Instantiate(prefab, spawnParent ? spawnParent : null);
            inst.name = prefab.name;
            Debug.Log("[AgentBundleLoader] ⚠ 沒有 RigLoader，直接生成。");
        }

        if (placeInFrontOfCamera && Camera.main)
        {
            var cam = Camera.main.transform;
            transform.position = cam.position + cam.forward * 2f;
            transform.rotation = Quaternion.LookRotation(cam.forward, Vector3.up);
        }
    }

    private void DetachFromCameraHierarchy()
    {
        for (var t = transform.parent; t != null; t = t.parent)
        {
            var n = t.name.ToLower();
            if (n.Contains("camera") || n.Contains("head") || n.Contains("xr origin"))
            {
                Debug.LogWarning($"[AgentBundleLoader] 物件位於 {t.name} 之下，已自動脫離以避免跟視角飄。");
                transform.SetParent(null, true);
                return;
            }
        }
    }

    private static bool VerifyMD5(string path, string expect)
    {
        try
        {
            using var md5 = MD5.Create();
            using var fs = File.OpenRead(path);
            var bytes = md5.ComputeHash(fs);
            var md5Str = BitConverter.ToString(bytes).Replace("-", "");
            return string.Equals(md5Str, expect, StringComparison.OrdinalIgnoreCase);
        }
        catch { return false; }
    }
}
