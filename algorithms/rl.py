"""
Author: Miguel Morales
BSD 3-Clause License

Copyright (c) 2018, Miguel Morales
All rights reserved.
https://github.com/mimoralea/gdrl/blob/master/LICENSE
"""

"""
modified by: John Mansfield

documentation added by: Gagandeep Randhawa
"""

"""
Model-free learning algorithms: Q-Learning and SARSA

Assumes no prior knowledge of the type of reward available to the agent.
Given enough episodes, tries to find an estimate of the optimal policy.
"""

from collections import deque

import numpy as np
from tqdm import tqdm
from utils.callbacks import MyCallbacks
from utils.decorators import print_runtime
import warnings


class RL:
    def __init__(self, env):
        self.env = env
        self.callbacks = MyCallbacks()
        self.render = False

    @staticmethod
    def decay_schedule(init_value, min_value, decay_ratio, max_steps, log_start=-2, log_base=10):
        """
        Parameters
        ----------------------------
        init_value {float}:
            Initial value of the quantity being decayed

        min_value {float}:
            Minimum value init_value is allowed to decay to

        decay_ratio {float}:
            The exponential factor exp(decay_ratio).
            Updated decayed value is calculated as

        max_steps {int}:
            Max iteration steps for decaying init_value

        log_start {array-like}, default = -2:
            Starting value of the decay sequence.
            Default value starts it at 0.01

        log_base {array-like}, default = 10:
            Base of the log space.


        Returns
        ----------------------------
        values {array-like}, shape(max_steps):
            Decay values where values[i] is the value used at i-th step
        """
        decay_steps = int(max_steps * decay_ratio)
        rem_steps = max_steps - decay_steps
        values = np.logspace(log_start, 0, decay_steps, base=log_base, endpoint=True)[::-1]
        values = (values - values.min()) / (values.max() - values.min())
        values = (init_value - min_value) * values + min_value
        values = np.pad(values, (0, rem_steps), 'edge')
    
        return values
    
    def evaluate_policy(self, pi, n_episodes=100):
        rewards = []
        for i in range(n_episodes):
            state, *_ = self.env.reset(seed=i)
            total_reward = 0

            while True:
                action = pi[state]
                state, reward, done, trauncated, *_ = self.env.step(action)
                total_reward += reward
                if done or trauncated:
                    break

            rewards.append(total_reward)

        return np.mean(rewards)

    def q_learning(self,
                   nS=None,
                   nA=None,
                   convert_state_obs=lambda state, done: state,
                   gamma=.99,
                   init_alpha=0.5,
                   min_alpha=0.01,
                   alpha_decay_ratio=0.5,
                   init_epsilon=1.0,
                   min_epsilon=0.1,
                   epsilon_decay_ratio=0.9,
                   n_episodes=10000):
        """
        Parameters
        ----------------------------
        nS {int}:
            Number of states

        nA {int}:
            Number of available actions

        convert_state_obs {lambda}:
            The state conversion utilized in BlackJack ToyText problem.
            Returns three state tuple as one of the 280 converted states.

        gamma {float}, default = 0.99:
            Discount factor

        init_alpha {float}, default = 0.5:
            Learning rate

        min_alpha {float}, default = 0.01:
            Minimum learning rate

        alpha_decay_ratio {float}, default = 0.5:
            Decay schedule of learing rate for future iterations

        init_epsilon {float}, default = 1.0:
            Initial epsilon value for epsilon greedy strategy.
            Chooses max(Q) over available actions with probability 1-epsilon.

        min_epsilon {float}, default = 0.1:
            Minimum epsilon. Used to balance exploration in later stages.

        epsilon_decay_ratio {float}, default = 0.9:
            Decay schedule of epsilon for future iterations

        n_episodes {int}, default = 10000:
            Number of episodes for the agent


        Returns
        ----------------------------
        Q {numpy array}, shape(nS, nA):
            Final action-value function Q(s,a)

        pi {lambda}, input state value, output action value:
            Policy mapping states to actions.

        V {numpy array}, shape(nS):
            State values array

        Q_track {numpy array}, shape(n_episodes, nS, nA):
            Log of Q(s,a) for each episode

        pi_track {list}, len(n_episodes):
            Log of complete policy for each episode
        """
        if nS is None:
            nS=self.env.observation_space.n
        if nA is None:
            nA=self.env.action_space.n

        #pi_track = []

        Q = np.zeros((nS, nA), dtype=np.float64)
        V = np.random.normal(size=(nS, ))
        #Q_track = np.zeros((n_episodes, nS, nA), dtype=np.float64)
        V_max_track = []
        # Explanation of lambda:
        # def select_action(state, Q, epsilon):
        #   if np.random.random() > epsilon:
        #       return np.argmax(Q[state])
        #   else:
        #       return np.random.randint(len(Q[state]))
        select_action = lambda state, Q, epsilon: np.argmax(Q[state]) \
            if np.random.random() > epsilon \
            else np.random.randint(len(Q[state]))
        alphas = RL.decay_schedule(init_alpha,
                                min_alpha,
                                alpha_decay_ratio,
                                n_episodes)
        epsilons = RL.decay_schedule(init_epsilon,
                                  min_epsilon,
                                  epsilon_decay_ratio,
                                  n_episodes)
        #pb = tqdm(range(n_episodes), leave=False)
        last_n_evals = deque(maxlen=100)
        max_v_cumavg = 0
        alpha = 0.99995
        trunc_count = 0
        reached_goal=0
        patiaence = 0
        for e in range(n_episodes):
            self.callbacks.on_episode_begin(self)
            self.callbacks.on_episode(self, episode=e)
            state, info = self.env.reset()
            done = False
            state = convert_state_obs(state, done)
            episode_reward = 0
            while not done:
                if self.render:
                    warnings.warn("Occasional render has been deprecated by openAI.  Use test_env.py to render.")
                #current_eps = min(min_epsilon, init_epsilon * (epsilon_decay_ratio ** (e + 1)))
                action = select_action(state, Q, epsilons[e])
                next_state, reward, terminated, truncated, _ = self.env.step(action)
                if reward > 0:
                    reached_goal += 1
                episode_reward += reward
                if truncated:
                    trunc_count += 1
                    warnings.warn("Episode was truncated.  Bootstrapping 0 reward.")
                done = terminated or truncated
                self.callbacks.on_env_step(self)
                next_state = convert_state_obs(next_state,done)
                td_target = reward + gamma * Q[next_state].max() * (not done)
                td_error = td_target - Q[state][action]
                Q[state][action] = Q[state][action] + alphas[e] * td_error
                state = next_state
            V_max_track.append(np.max(Q).astype(np.float32))
            #pi_track.append(np.argmax(Q, axis=1))
            self.render = False
            self.callbacks.on_episode_end(self)

            
            max_V = np.max(Q)
            new_max_v_cumavg = max_v_cumavg + (max_V - max_v_cumavg) / (e + 1)

            rdiff = np.abs(new_max_v_cumavg - max_v_cumavg) / np.abs(max_v_cumavg)
            adiff = np.abs(new_max_v_cumavg - max_v_cumavg)

            if rdiff < 1e-6:
                patiaence += 1
                if patiaence >= 10000:
                    #print("Early stopping ...")
                    break
            else:
                patiaence = 0

            max_v_cumavg = new_max_v_cumavg

            #pb.set_description(f"{max_v_cumavg}, {rdiff}, {patiaence}")

        #pb.close()
        V = np.max(Q, axis=1)

        pi = {s: a for s, a in enumerate(np.argmax(Q, axis=1))}
        pi_fn = lambda s: pi[s]
        return Q, V, pi_fn, np.asarray(V_max_track)#, pi_track[:e]

    @print_runtime
    def sarsa(self,
              nS=None,
              nA=None,
              convert_state_obs=lambda state, done: state,
              gamma=.99,
              init_alpha=0.5,
              min_alpha=0.01,
              alpha_decay_ratio=0.5,
              init_epsilon=1.0,
              min_epsilon=0.1,
              epsilon_decay_ratio=0.9,
              n_episodes=10000):
        """
        Parameters
        ----------------------------
        nS {int}:
            Number of states

        nA {int}:
            Number of available actions

        convert_state_obs {lambda}:
            The state conversion utilized in BlackJack ToyText problem.
            Returns three state tuple as one of the 280 converted states.

        gamma {float}, default = 0.99:
            Discount factor

        init_alpha {float}, default = 0.5:
            Learning rate

        min_alpha {float}, default = 0.01:
            Minimum learning rate

        alpha_decay_ratio {float}, default = 0.5:
            Decay schedule of learing rate for future iterations

        init_epsilon {float}, default = 1.0:
            Initial epsilon value for epsilon greedy strategy.
            Chooses max(Q) over available actions with probability 1-epsilon.

        min_epsilon {float}, default = 0.1:
            Minimum epsilon. Used to balance exploration in later stages.

        epsilon_decay_ratio {float}, default = 0.9:
            Decay schedule of epsilon for future iterations

        n_episodes {int}, default = 10000:
            Number of episodes for the agent


        Returns
        ----------------------------
        Q {numpy array}, shape(nS, nA):
            Final action-value function Q(s,a)

        pi {lambda}, input state value, output action value:
            Policy mapping states to actions.

        V {numpy array}, shape(nS):
            State values array

        Q_track {numpy array}, shape(n_episodes, nS, nA):
            Log of Q(s,a) for each episode

        pi_track {list}, len(n_episodes):
            Log of complete policy for each episode
        """
        if nS is None:
            nS = self.env.observation_space.n
        if nA is None:
            nA = self.env.action_space.n
        pi_track = []
        Q = np.zeros((nS, nA), dtype=np.float64)
        Q_track = np.zeros((n_episodes, nS, nA), dtype=np.float64)
        # Explanation of lambda:
        # def select_action(state, Q, epsilon):
        #   if np.random.random() > epsilon:
        #       return np.argmax(Q[state])
        #   else:
        #       return np.random.randint(len(Q[state]))
        select_action = lambda state, Q, epsilon: np.argmax(Q[state]) \
            if np.random.random() > epsilon \
            else np.random.randint(len(Q[state]))
        alphas = RL.decay_schedule(init_alpha,
                                min_alpha,
                                alpha_decay_ratio,
                                n_episodes)
        epsilons = RL.decay_schedule(init_epsilon,
                                  min_epsilon,
                                  epsilon_decay_ratio,
                                  n_episodes)

        pb = tqdm(range(n_episodes), leave=False)
        for e in pb:
            self.callbacks.on_episode_begin(self)
            self.callbacks.on_episode(self, episode=e)
            state, info = self.env.reset()
            done = False
            state = convert_state_obs(state, done)
            action = select_action(state, Q, epsilons[e])
            while not done:
                if self.render:
                    warnings.warn("Occasional render has been deprecated by openAI.  Use test_env.py to render.")
                next_state, reward, terminated, truncated, _ = self.env.step(action)
                if truncated:
                    warnings.warn("Episode was truncated.  Bootstrapping 0 reward.")
                done = terminated or truncated
                self.callbacks.on_env_step(self)
                next_state = convert_state_obs(next_state, done)
                next_action = select_action(next_state, Q, epsilons[e])
                td_target = reward + gamma * Q[next_state][next_action] * (not done)
                td_error = td_target - Q[state][action]
                Q[state][action] = Q[state][action] + alphas[e] * td_error
                state, action = next_state, next_action
            Q_track[e] = Q
            pi_track.append(np.argmax(Q, axis=1))
            self.render = False
            self.callbacks.on_episode_end(self)

        V = np.max(Q, axis=1)

        pi = {s: a for s, a in enumerate(np.argmax(Q, axis=1))}
        return Q, V, pi, Q_track, pi_track
