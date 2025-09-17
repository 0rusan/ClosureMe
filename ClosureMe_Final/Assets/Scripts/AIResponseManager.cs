using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Collections.Generic;

public class AIResponseManager : MonoBehaviour
{
    public DialogueUI dialogueUI;
    public TalkTrigger talkTrigger; // 新增引用：回傳狀態給 TalkTrigger
    public TTSAPI ttsAPI;
    public string apiUrl = "http://122.100.76.28:80/chatbot/chat";

    public void AskAI(string message)
    {
        StartCoroutine(SendToAI(message));
    }

    IEnumerator SendToAI(string message)
    {
        if (message == "~INIT~")
        {
            if (talkTrigger != null) talkTrigger.OnAIResponseFinished();
            yield break;
        }
        string json = JsonUtility.ToJson(new MessagePayload { message = message });
        using (UnityWebRequest request = new UnityWebRequest(apiUrl, "POST"))
        {
            byte[] body = System.Text.Encoding.UTF8.GetBytes(json);
            request.uploadHandler = new UploadHandlerRaw(body);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string result = request.downloadHandler.text;
                AIReply replyObj = JsonUtility.FromJson<AIReply>(result);

                if (dialogueUI != null && !string.IsNullOrEmpty(replyObj.reply))
                {
                    dialogueUI.StartDialogue(new List<string> { replyObj.reply });
                    StartCoroutine(ttsAPI.SendTTSRequest(replyObj.reply));
                }
            }
            else
            {
                dialogueUI.StartDialogue(new List<string> { "你好" + message });
                StartCoroutine(ttsAPI.SendTTSRequest("你好" + message));

            }

            // 無論成功或失敗，通知 TalkTrigger 結束等待
            if (talkTrigger != null) talkTrigger.OnAIResponseFinished();
            // 顯示 AI 回應，並通知 TalkTrigger
        }
    }


    [System.Serializable]
    public class MessagePayload
    {
        public string message;
    }

    [System.Serializable]
    public class AIReply
    {
        public string reply;
    }
}