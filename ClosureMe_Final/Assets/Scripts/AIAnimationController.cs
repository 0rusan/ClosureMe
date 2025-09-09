using UnityEngine;

public class AIAnimationController : MonoBehaviour
{
    public enum AIState { Idle, Walk, Thinking, Talking }

    private Animator animator;
    private AIState currentState = AIState.Idle;

    void Awake()
    {
        animator = GetComponent<Animator>();
    }

    public void SetAIState(AIState newState)
    {
        if (currentState == newState) return;
        currentState = newState;

        animator.SetBool("isWalking", newState == AIState.Walk);
        animator.SetBool("isThinking", newState == AIState.Thinking);
        animator.SetBool("isTalking", newState == AIState.Talking);
    }

    public bool IsConversing()
    {
        return currentState == AIState.Thinking || currentState == AIState.Talking;
    }

    public void ResetToIdle()
    {
        currentState = AIState.Idle;
        animator.SetBool("isWalking", false);
        animator.SetBool("isThinking", false);
        animator.SetBool("isTalking", false);
    }
}