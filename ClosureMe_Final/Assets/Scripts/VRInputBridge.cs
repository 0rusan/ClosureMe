using UnityEngine;
using UnityEngine.InputSystem;

public class VRInputBridge : MonoBehaviour
{
    [Header("Target")]
    public TalkTrigger talk;   // 指到場景裡的 TalkTrigger

    [Header("XRI Actions (X/A/B)")]
    // 左手 X（互動 = E）
    public InputActionReference left_X_primaryButton;      // XRI LeftHand Interaction / primaryButton
    // 右手 A（錄音：按下開始、放開結束 = R）
    public InputActionReference right_A_primaryButton;     // XRI RightHand Interaction / primaryButton
    // 右手 B（結束 / 取消 = T / Esc）
    public InputActionReference right_B_secondaryButton;   // XRI RightHand Interaction / secondaryButton

    void OnEnable()
    {
        if (left_X_primaryButton)
        {
            left_X_primaryButton.action.performed += OnXPerformed;
            left_X_primaryButton.action.Enable();
        }
        if (right_A_primaryButton)
        {
            right_A_primaryButton.action.started += OnAStarted;   // 按下開始錄音
            right_A_primaryButton.action.canceled += OnACanceled;  // 放開結束錄音
            right_A_primaryButton.action.Enable();
        }
        if (right_B_secondaryButton)
        {
            right_B_secondaryButton.action.performed += OnBPerformed; // 結束/取消
            right_B_secondaryButton.action.Enable();
        }
    }

    void OnDisable()
    {
        if (left_X_primaryButton)
        {
            left_X_primaryButton.action.performed -= OnXPerformed;
            left_X_primaryButton.action.Disable();
        }
        if (right_A_primaryButton)
        {
            right_A_primaryButton.action.started -= OnAStarted;
            right_A_primaryButton.action.canceled -= OnACanceled;
            right_A_primaryButton.action.Disable();
        }
        if (right_B_secondaryButton)
        {
            right_B_secondaryButton.action.performed -= OnBPerformed;
            right_B_secondaryButton.action.Disable();
        }
    }

    void OnXPerformed(InputAction.CallbackContext _)
    {
        if (DoorController.Current != null)
        {
            DoorController.Current.VR_ToggleDoor();
            // Debug.Log("VR X: Toggle Door");
        }
        else
        {
            talk?.VR_Interact();
            // Debug.Log("VR X: Talk Interact");
        }
    }

    void OnAStarted(InputAction.CallbackContext _) { talk?.VR_RecordStart(); }
    void OnACanceled(InputAction.CallbackContext _) { talk?.VR_RecordStop(); }
    void OnBPerformed(InputAction.CallbackContext _) { talk?.VR_Cancel(); }
}