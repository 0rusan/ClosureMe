using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class HttpSceneSelector : MonoBehaviour
{
    public string txtUrl = "http://192.168.1.102/models/environment.txt"; //伺服器
    public float pollSec = 1.0f;
    public MapManager mapManager;   // 指到你現有的 MapManager
    public string[] trimToLower = new[] { "\r", "\n", " " };

    string lastKey = null;

    void OnEnable() => StartCoroutine(Poll());
    IEnumerator Poll()
    {
        while (true)
        {
            using (var req = UnityWebRequest.Get(txtUrl))
            {
                yield return req.SendWebRequest();
                if (req.result == UnityWebRequest.Result.Success)
                {
                    var key = (req.downloadHandler.text ?? "").Trim().ToLowerInvariant();
                    foreach (var t in trimToLower) key = key.Replace(t, "");
                    if (!string.IsNullOrEmpty(key) && key != lastKey)
                    {
                        lastKey = key;
                        // key 直接當場景名，或你可做一個字典映射
                        StartCoroutine(mapManager.SwitchTo(KeyToSceneName(key)));
                    }
                }
            }
            yield return new WaitForSeconds(pollSec);
        }
    }
    string KeyToSceneName(string key)
    {
        switch (key)
        {
            case "park": return "公園究極版";
            case "meetingroom": return "最終品";
            case "library": return "圖書館";
            default: return key; // 已經是場景名就直接用
        }
    }
}
