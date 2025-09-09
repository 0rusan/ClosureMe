using UnityEngine;
using TMPro;
using System.Collections.Generic;

public class DialogueUI : MonoBehaviour
{
    public GameObject panel;
    public TextMeshProUGUI dialogueText;

    private bool isActive = false;

    void Awake()
    {
        EndDialogue();
    }

    public void StartDialogue(List<string> dialogueLines)
    {
        if (dialogueLines == null || dialogueLines.Count == 0) return;

        panel.SetActive(true);
        isActive = true;
        dialogueText.text = dialogueLines[0]; // 只顯示第一句（你每次都只給一段）
    }

    public void EndDialogue()
    {
        panel.SetActive(false);
        isActive = false;
    }

    public bool IsDialogueActive()
    {
        return isActive;
    }
}