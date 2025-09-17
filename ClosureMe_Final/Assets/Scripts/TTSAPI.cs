using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.IO;
using System.Text.RegularExpressions;

public class TTSAPI : MonoBehaviour
{
    [Header("Server")]
    public string ttsUrl = "http://192.168.1.102/tts";

    [Header("Audio")]
    public AudioSource audioSource;
    [Tooltip("後端輸出檔名（若你後端固定寫 output.wav）")]
    public string outputFileName = "output.wav";

    [Tooltip("在 file:// 讀檔時加上 cache-buster，避免播放到舊檔")]
    public bool useCacheBuster = true;

    [Tooltip("若檔案尚未落盤，重試讀取次數")]
    public int readRetries = 10;

    [Tooltip("每次重試的間隔秒數")]
    public float retryInterval = 0.05f;

    public IEnumerator SendTTSRequest(string text)
    {
        if (string.IsNullOrEmpty(text))
            yield break;

        // 1) 送出 TTS 請求（JSON）
        var payload = JsonUtility.ToJson(new TTSRequest { text = text });
        string responseBody = null;
        using (var req = new UnityWebRequest(ttsUrl, "POST"))
        {
            req.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(payload));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 180;

            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                string body = req.downloadHandler != null ? req.downloadHandler.text : "";
                Debug.LogError($"[TTS] HTTP Error: {req.error}\nServer says: {body}");
                yield break;
            }
            responseBody = req.downloadHandler.text;
        }

        // 2) 解析 url，若有就直接 HTTP 抓音檔；沒有則退回舊的 file://
        string audioUrl = ExtractJsonValue(responseBody, "url");

        if (!string.IsNullOrEmpty(audioUrl))
        {
            using (var www = UnityWebRequestMultimedia.GetAudioClip(audioUrl, AudioType.WAV))
            {
                www.timeout = 30;
                yield return www.SendWebRequest();

                if (www.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError("[TTS] 下載音檔失敗：" + www.error);
                    yield break;
                }

                var clip = DownloadHandlerAudioClip.GetContent(www);
                PlayClip(clip);
                yield break;
            }
        }

        // ---- fallback: 舊流程，從 StreamingAssets 播放本機檔案 ----
        string diskPath = Path.Combine(Application.streamingAssetsPath, outputFileName);
        string url = "file://" + diskPath + (useCacheBuster ? $"?cb={Time.realtimeSinceStartup:F3}" : "");

        int tries = 0;
        while (!File.Exists(diskPath) && tries < readRetries)
        {
            tries++;
            yield return new WaitForSeconds(retryInterval);
        }

        using (var www = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
        {
            www.timeout = 30;
            yield return www.SendWebRequest();

            if (www.result != UnityWebRequest.Result.Success)
            {
                bool ok = false;
                for (int i = 0; i < readRetries && !ok; i++)
                {
                    yield return new WaitForSeconds(retryInterval);
                    using (var retry = UnityWebRequestMultimedia.GetAudioClip(url, AudioType.WAV))
                    {
                        retry.timeout = 30;
                        yield return retry.SendWebRequest();
                        if (retry.result == UnityWebRequest.Result.Success)
                        {
                            var clip2 = DownloadHandlerAudioClip.GetContent(retry);
                            PlayClip(clip2);
                            ok = true;
                        }
                    }
                }
                if (!ok)
                {
                    Debug.LogError("[TTS] 讀取/播放音訊失敗：" + www.error);
                }
            }
            else
            {
                var clip = DownloadHandlerAudioClip.GetContent(www);
                PlayClip(clip);
            }
        }
    }

    private void PlayClip(AudioClip clip)
    {
        if (clip == null) return;
        if (audioSource == null) audioSource = gameObject.GetComponent<AudioSource>();
        if (audioSource == null) audioSource = gameObject.AddComponent<AudioSource>();

        audioSource.Stop();
        audioSource.clip = clip;
        audioSource.Play();
    }

    [System.Serializable]
    public class TTSRequest
    {
        public string text;
    }

    // 取回 JSON 中的字串欄位值（不引入 JSON 解析器，保持最少依賴）
    private static string ExtractJsonValue(string json, string key)
    {
        var m = Regex.Match(json ?? "", $"\"{key}\"\\s*:\\s*\"([^\"]*)\"");
        return m.Success ? m.Groups[1].Value : "";
    }
}
