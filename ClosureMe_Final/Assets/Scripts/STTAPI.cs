using UnityEngine;
using UnityEngine.Networking;
using System;
using System.Collections;
using System.Threading.Tasks;

public class STTAPI : MonoBehaviour
{
    [Header("STT Server")]
    public string baseUrl = "http://122.100.76.28:80/tts";
    public string sttEndpoint = "/stt";

    [Header("Record")]
    public string micDevice;
    public int targetSampleRate = 16000; // 後端要求 16k

    public bool IsRecording { get; private set; }

    private AudioClip _clip;
    private string _activeMic;

    // ---- 錄音 ----
    public void BeginRecording(int maxSeconds = 30)
    {
        if (IsRecording) return;

        if (Microphone.devices.Length == 0)
        {
            Debug.LogError("[STT] 沒有偵測到麥克風裝置");
            return;
        }
        _activeMic = string.IsNullOrEmpty(micDevice) ? Microphone.devices[0] : micDevice;

        // 這裡的 sampleRate 用裝置支援的較穩（讓 Unity 幫你取樣）
        int sysRate = AudioSettings.outputSampleRate; // e.g. 48000
        _clip = Microphone.Start(_activeMic, false, maxSeconds, sysRate);
        IsRecording = true;
        Debug.Log($"[STT] 開始錄音 (device: {_activeMic}, systemRate: {sysRate})");
    }

    // ---- 停止 + 上傳 ----
    public IEnumerator StopAndTranscribe(Action<string> onText)
    {
        if (!IsRecording) yield break;

        // 等至少有一幀
        while (Microphone.GetPosition(_activeMic) <= 0) yield return null;

        Microphone.End(_activeMic);
        IsRecording = false;
        Debug.Log("[STT] 錄音結束，開始轉檔與上傳…");

        // ====== 主執行緒：先把 Unity 相關資料通通讀出來 ======
        int srcSamples = _clip.samples;
        int srcChannels = _clip.channels;
        int srcHz = _clip.frequency;              // 只能在主執行緒讀
        float[] interleaved = new float[srcSamples * srcChannels];
        _clip.GetData(interleaved, 0);            // 只能在主執行緒呼叫

        // ====== 背景執行緒：僅操作純陣列 ======
        byte[] wavBytes = null;
        bool encodeOk = true;

        yield return RunOnThreadPool(() =>
        {
            try
            {
                // 1) 轉單聲道
                float[] mono = ToMono(interleaved, srcChannels);
                // 2) 若需要，重採樣到目標 16k
                float[] mono16k = (srcHz == targetSampleRate) ? mono : ResampleLinear(mono, srcHz, targetSampleRate);
                // 3) 寫成 WAV bytes（PCM16）
                wavBytes = EncodeWavPcm16(mono16k, targetSampleRate);
            }
            catch (Exception e)
            {
                encodeOk = false;
                Debug.LogError("[STT] WAV 編碼失敗 : " + e);
            }
        });

        if (!encodeOk || wavBytes == null)
        {
            onText?.Invoke(string.Empty);
            yield break;
        }

        // ====== 上傳到後端 ======
        WWWForm form = new WWWForm();
        // ★ 伺服器欄位名要用 "wav"（不是 "audio"）
        form.AddBinaryData("audio", wavBytes, "record.wav", "audio/wav");
        // 可選：指定語言（伺服器支援 "lang"）
        form.AddField("lang", "zh");

        // 組 URL（避免重複斜線）
        var url = $"{baseUrl.TrimEnd('/')}{(sttEndpoint.StartsWith("/") ? sttEndpoint : "/" + sttEndpoint)}";
        using (var req = UnityWebRequest.Post(url, form))
        {
            req.timeout = 15;
            Debug.Log($"[STT] POST {url}  bytes={wavBytes?.Length}");

            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"[STT] HTTP error: {req.result} code={req.responseCode} url={url} err={req.error}");
                Debug.LogError($"[STT] resp: {req.downloadHandler.text}");
                onText?.Invoke(string.Empty);
                yield break;
            }

            // 伺服器回 {"ok":true,"text":"..."}，簡單取出
            string text = ExtractJsonValue(req.downloadHandler.text, "text");
            onText?.Invoke(text);
        }
    }

    // ---- Utils ----

    // 把交錯(interleaved)多聲道資料轉成單聲道（簡單平均）
    private static float[] ToMono(float[] interleaved, int channels)
    {
        if (channels == 1) return (float[])interleaved.Clone();

        int frames = interleaved.Length / channels;
        float[] mono = new float[frames];

        int idx = 0;
        for (int i = 0; i < frames; i++)
        {
            float sum = 0f;
            for (int c = 0; c < channels; c++)
                sum += interleaved[idx++];
            mono[i] = sum / channels;
        }
        return mono;
    }

    // 簡單線性重採樣
    private static float[] ResampleLinear(float[] src, int srcHz, int dstHz)
    {
        if (srcHz == dstHz) return (float[])src.Clone();

        double ratio = (double)dstHz / srcHz;
        int dstLen = (int)Math.Round(src.Length * ratio);
        float[] dst = new float[dstLen];

        for (int i = 0; i < dstLen; i++)
        {
            double srcPos = i / ratio;
            int p = (int)srcPos;
            double frac = srcPos - p;
            float s0 = src[Mathf.Clamp(p, 0, src.Length - 1)];
            float s1 = src[Mathf.Clamp(p + 1, 0, src.Length - 1)];
            dst[i] = (float)(s0 + (s1 - s0) * frac);
        }
        return dst;
    }

    // PCM16 WAV
    private static byte[] EncodeWavPcm16(float[] mono, int sampleRate)
    {
        short[] pcm16 = new short[mono.Length];
        for (int i = 0; i < mono.Length; i++)
        {
            float v = Mathf.Clamp(mono[i], -1f, 1f);
            pcm16[i] = (short)Mathf.RoundToInt(v * 32767f);
        }

        int dataLen = pcm16.Length * 2;
        byte[] header = new byte[44];
        // RIFF
        WriteAscii(header, 0, "RIFF");
        BitConverter.GetBytes(36 + dataLen).CopyTo(header, 4);
        WriteAscii(header, 8, "WAVE");
        // fmt
        WriteAscii(header, 12, "fmt ");
        BitConverter.GetBytes(16).CopyTo(header, 16);        // PCM chunk size
        BitConverter.GetBytes((short)1).CopyTo(header, 20);  // PCM
        BitConverter.GetBytes((short)1).CopyTo(header, 22);  // mono
        BitConverter.GetBytes(sampleRate).CopyTo(header, 24);
        BitConverter.GetBytes(sampleRate * 2).CopyTo(header, 28); // byte rate
        BitConverter.GetBytes((short)2).CopyTo(header, 32);       // block align
        BitConverter.GetBytes((short)16).CopyTo(header, 34);      // bits
        // data
        WriteAscii(header, 36, "data");
        BitConverter.GetBytes(dataLen).CopyTo(header, 40);

        byte[] wav = new byte[44 + dataLen];
        Buffer.BlockCopy(header, 0, wav, 0, 44);
        Buffer.BlockCopy(pcm16, 0, wav, 44, dataLen);
        return wav;
    }

    private static void WriteAscii(byte[] buf, int offset, string s)
    {
        var b = System.Text.Encoding.ASCII.GetBytes(s);
        Buffer.BlockCopy(b, 0, buf, offset, b.Length);
    }

    private static IEnumerator RunOnThreadPool(Action action)
    {
        Exception ex = null;
        var t = Task.Run(() =>
        {
            try { action(); }
            catch (Exception e) { ex = e; }
        });
        while (!t.IsCompleted) yield return null;
        if (ex != null) throw ex;
    }

    private static string ExtractJsonValue(string json, string key)
    {
        var m = System.Text.RegularExpressions.Regex.Match(json, $"\"{key}\"\\s*:\\s*\"([^\"]*)\"");
        return m.Success ? m.Groups[1].Value : "";
    }
}
