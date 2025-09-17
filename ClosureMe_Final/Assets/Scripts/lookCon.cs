using UnityEngine;

public class lookCon : MonoBehaviour
{
    // 滑鼠靈敏度
    public float MouseSensitivity = 200.0f;
    // 儲存攝影機X軸方向的角度
    float CameraX = 0.0f;
    // 視角上下移動之最大、最小值
    float CameraXMax = 60f;
    float CameraXMin = -60f;
    // 玩家
    public Transform playerT = null;
    void Start()
    {
        // 滑鼠鎖定，避免出現
        Cursor.lockState = CursorLockMode.Locked;
    }
    void Update()
    {
        // 滑鼠偏移量：水平、垂直
        float mouseX = Input.GetAxis("Mouse X") * Time.deltaTime * MouseSensitivity;
        float mouseY = Input.GetAxis("Mouse Y") * Time.deltaTime * MouseSensitivity;
        // 視角的上下移動，由滑鼠y軸改變，攝影機需要繞x軸旋轉
        CameraX -= mouseY;
        // 在最大值、最小值之間取值
        CameraX = Mathf.Clamp(CameraX, CameraXMin, CameraXMax);
        // 攝影機旋轉：localRotation相對於父物體旋轉
        transform.localRotation = Quaternion.Euler(CameraX, 0, 0);
        // 視角的左右移動，一般都是360度旋轉，不需要額外的變量儲存

        // 由滑鼠的X座標決定，攝影機需要繞Y軸旋轉，人物也需要轉
        // 但是攝影機是玩家的子物體，玩家旋轉，攝影機就會跟著轉
        if (playerT != null)
        {
            // 在現有的基礎之上旋轉
            playerT.Rotate(playerT.up, mouseX);
        }
    }
}