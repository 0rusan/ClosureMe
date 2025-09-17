using UnityEngine;
using TMPro;
using UnityEngine.EventSystems;

public class moveCon : MonoBehaviour
{

    public float walkSpeed = 5f;
    private Rigidbody rb;

    [Header("輸入欄檢查")]
    public TMP_InputField playerInputField; // 從 Inspector 指定輸入欄

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void FixedUpdate()
    {
        if (IsInputFieldFocused())
            return;


        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");

        Vector3 moveDir = transform.forward * v + transform.right * h;
        Vector3 move = moveDir.normalized * walkSpeed;


        //正確用法：Rigidbody.velocity
        //b.velocity = new Vector3(move.x, rb.velocity.y, move.z); // 保留 y 軸重力


        rb.linearVelocity = new Vector3(move.x, rb.linearVelocity.y, move.z); // 保留 y 軸重力
    }
    private bool IsInputFieldFocused()
    {
        if (EventSystem.current == null) return false;

        GameObject selected = EventSystem.current.currentSelectedGameObject;
        return selected != null && selected.GetComponent<TMP_InputField>() != null;
    }
}