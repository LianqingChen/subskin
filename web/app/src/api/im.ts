import apiClient from './client'

export const imApi = {
  getConversations: () => apiClient.get('/im/conversations'),
  createPrivateChat: (userId: number) =>
    apiClient.post('/im/conversations/private', { user_id: userId }),
  getMessages: (convId: number, beforeId?: number) =>
    apiClient.get(`/im/conversations/${convId}/messages`, {
      params: { before_id: beforeId, limit: 50 },
    }),
  markRead: (convId: number) =>
    apiClient.post(`/im/conversations/${convId}/read`),
  togglePin: (convId: number) =>
    apiClient.post(`/im/conversations/${convId}/pin`),

  sendMessage: (data: {
    conversation_id: number
    msg_type: string
    content?: string
    metadata?: any
    reply_to_id?: number
  }) => apiClient.post('/im/messages', data),
  recallMessage: (msgId: number) =>
    apiClient.post(`/im/messages/${msgId}/recall`),

  sendFriendRequest: (userId: number, message?: string) =>
    apiClient.post('/im/friends/request', { user_id: userId, message }),
  getFriendRequests: () => apiClient.get('/im/friends/requests'),
  acceptRequest: (reqId: number) =>
    apiClient.post(`/im/friends/requests/${reqId}/accept`),
  declineRequest: (reqId: number) =>
    apiClient.post(`/im/friends/requests/${reqId}/decline`),
  getFriends: () => apiClient.get('/im/friends'),

  createGroup: (name: string, memberIds: number[]) =>
    apiClient.post('/im/groups', { name, member_ids: memberIds }),
  getGroupMembers: (groupId: number) =>
    apiClient.get(`/im/groups/${groupId}/members`),
  addGroupMembers: (groupId: number, userIds: number[]) =>
    apiClient.post(`/im/groups/${groupId}/members`, { user_ids: userIds }),
  removeGroupMember: (groupId: number, userId: number) =>
    apiClient.delete(`/im/groups/${groupId}/members/${userId}`),
  updateGroupInfo: (groupId: number, data: { name?: string; announcement?: string }) =>
    apiClient.put(`/im/groups/${groupId}/info`, null, { params: data }),

  sharePost: (postId: number, conversationId: number) =>
    apiClient.post('/im/share/post', { post_id: postId, conversation_id: conversationId }),

  matchContacts: (phoneHashes: Array<{ hash: string; name?: string }>) =>
    apiClient.post('/im/contacts/match', { phone_hashes: phoneHashes }),
  searchUsers: (q: string) =>
    apiClient.get('/im/contacts/search', { params: { q, limit: 20 } }),
}
