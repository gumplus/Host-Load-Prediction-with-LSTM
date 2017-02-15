from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
from utils import read_data
import numpy as np
from scipy import linalg
import pickle

#from pastalog import Log

flags = tf.flags
logging = tf.logging
flags.DEFINE_string("data_path", "/home/tyrion/lannister/1024/tyrion.pkl", 
                    "The path of host load data")
flags.DEFINE_string("ae_path", "high", "The path of weight and bias")
flags.DEFINE_integer("input_dim", 64, "The length of history window")
flags.DEFINE_integer("ae_dim", 200, "The length of autoencoder hidden layer size")
flags.DEFINE_integer("hidden_dim", 100, "The length of hidden layer size")
flags.DEFINE_integer("output_dim", 6, "The length of prediction window")
flags.DEFINE_integer("batch_size", 128, "Mini-batch size")
flags.DEFINE_integer("epoch", 90, "The total epochs")
flags.DEFINE_float("lr", 0.05, "Learning rate")
flags.DEFINE_integer("max_grad_norm", 5, "max grad norm")
FLAGS = flags.FLAGS

def get_ae_weight():
    with open("./1024/"+FLAGS.ae_path+"/weights.pkl", 'rb') as input_1:
        ae_weight = pickle.load(input_1)
    with open("./1024/"+FLAGS.ae_path+"/biases.pkl", 'rb') as input_2:
        ae_bias = pickle.load(input_2)
    
    return (ae_weight, ae_bias)
    
class ESN(object):
    def __init__(self, is_training, length, leaking_rate=0.2, initLen=100):
        self.batch_size = batch_size = FLAGS.batch_size
        self.num_steps = num_steps = length
        self.inSize = inSize = FLAGS.input_dim
        self.Win_inSize = Win_inSize = FLAGS.ae_dim
        self.resSize = resSize = FLAGS.hidden_dim
        
        self._input_data = tf.placeholder(tf.float32, [batch_size, length, FLAGS.input_dim])
        if is_training:
            self._targets = tf.placeholder(tf.float32, [batch_size, length-initLen, FLAGS.output_dim])
        else:
            self._targets = tf.placeholder(tf.float32, [batch_size, length, FLAGS.output_dim])
        self._ae_weights = tf.placeholder(tf.float32, [FLAGS.input_dim, FLAGS.ae_dim])
        self._ae_biases = tf.placeholder(tf.float32, [FLAGS.ae_dim])
        
        self._Win = Win = tf.placeholder(tf.float32, [Win_inSize, resSize])
        self._W = W = tf.placeholder(tf.float32, [resSize, resSize])
        
        self._initial_state = np.zeros((batch_size, resSize), dtype=np.float32)

        S = []
        s = self._initial_state
        
        with tf.variable_scope("ESN"):
            for i in range(num_steps):
                ae_out = tf.nn.sigmoid(tf.add(tf.matmul(self._input_data[:,i,:], 
                                                        self._ae_weights), 
                                              self._ae_biases))
                s = (1 - leaking_rate) * s + \
                leaking_rate * tf.nn.tanh(tf.matmul(ae_out, Win)+tf.matmul(s,W))
                if is_training:
                    if i>= initLen:
                        S.append(tf.concat(1, [self._input_data[:,i,:], s]))
                else:
                    S.append(tf.concat(1, [self._input_data[:,i,:], s]))
        self._final_state = s
        
        V_size = inSize + resSize
        hidden_output = tf.reshape(tf.concat(1, S), [-1, V_size])
        
        V = tf.get_variable("v", shape=[V_size, FLAGS.output_dim], dtype=tf.float32, 
            initializer=tf.random_uniform_initializer(-tf.sqrt(1./V_size),tf.sqrt(1./V_size)))
        b = tf.get_variable("b", shape=[FLAGS.output_dim], dtype=tf.float32, 
            initializer=tf.constant_initializer(0.1))
        logits = tf.add(tf.matmul(hidden_output, V), b)
        
        target = tf.reshape(self._targets, [-1, FLAGS.output_dim])
        training_loss = tf.reduce_sum(tf.pow(logits-target, 2)) / 2        
        mse = tf.reduce_mean(tf.pow(logits-target, 2))        
        self._cost = mse
        
        if not is_training:
            return
        
        self._lr = tf.Variable(0.0, trainable=False)
        tvars = tf.trainable_variables()
        grads, _ = tf.clip_by_global_norm(tf.gradients(training_loss, tvars), FLAGS.max_grad_norm)
        optimizer = tf.train.GradientDescentOptimizer(self.lr)
        self._train_op = optimizer.apply_gradients(zip(grads, tvars))
        
    def assign_lr(self, session, lr_value):
        session.run(tf.assign(self.lr, lr_value))
        
    @property
    def input_data(self):
        return self._input_data
        
    @property
    def Win(self):
        return self._Win
        
    @property
    def W(self):
        return self._W
        
    @property
    def targets(self):
        return self._targets
        
    @property
    def ae_weights(self):
        return self._ae_weights
        
    @property
    def ae_biases(self):
        return self._ae_biases
        
    @property
    def initial_state(self):
        return self._initial_state
        
    @property
    def cost(self):
        return self._cost
        
    @property
    def final_state(self):
        return self._final_state
        
    @property
    def lr(self):
        return self._lr
        
    @property
    def train_op(self):
        return self._train_op
    
def run_train_epoch(session, m, Win, W, data_x, data_y, ae_weight, ae_bias, eval_op):
    costs = []
    states = []
    for i in xrange(int(len(data_y) / FLAGS.batch_size)):
        cost, state, _ = session.run(
            [m.cost, m.final_state, eval_op],
            {m.Win: Win,
             m.W: W,
             m.input_data: data_x[i*FLAGS.batch_size:(i+1)*FLAGS.batch_size],
             m.targets: data_y[i*FLAGS.batch_size:(i+1)*FLAGS.batch_size],
             m.ae_weights: ae_weight,
             m.ae_biases: ae_bias})
        costs.append(cost)
        states.append(state)
    return (sum(costs)/len(costs), states)
    
def run_test_epoch(session, m, Win, W, data_x, data_y, ae_weight, ae_bias, eval_op, train_state):
    costs = []
    states = []
    for i in xrange(int(len(data_y) / FLAGS.batch_size)):
        cost, state, _ = session.run(
            [m.cost, m.final_state, eval_op],
            {m.Win: Win,
             m.W: W,
             m.input_data: data_x[i*FLAGS.batch_size:(i+1)*FLAGS.batch_size],
             m.targets: data_y[i*FLAGS.batch_size:(i+1)*FLAGS.batch_size],
             m.ae_weights: ae_weight,
             m.ae_biases: ae_bias})
        costs.append(cost)
        states.append(state)
    return (sum(costs)/len(costs), states)    

def main(_):
    print("===============================================================================")
    print("The input_dim is", FLAGS.input_dim, "The hidden_dim is", FLAGS.hidden_dim)
    print("The output_dim is", FLAGS.output_dim, "The batch_size is", FLAGS.batch_size)
    print("The ae_path is", FLAGS.ae_path)
    print("The data_path is", FLAGS.data_path)
    X_train, y_train, X_test, y_test, _, cpu_load_std = read_data(FLAGS.data_path,
                                                                  FLAGS.input_dim, 
                                                                  FLAGS.output_dim,
                                                                  32)
    
    Win_inSize = FLAGS.ae_dim
    resSize = FLAGS.hidden_dim
    rho = 0.1
#    rho = 0.9
    cr = 0.05
    Win = np.float32(np.random.rand(Win_inSize, resSize)/5 - 0.1)
#    Win = np.float32(np.random.rand(Win_inSize, resSize) - 0.5)
    N = resSize * resSize
    W = np.random.rand(N) - 0.5
    zero_index = np.random.permutation(N)[int(N * cr * 1.0):]
    W[zero_index] = 0
    W = W.reshape((resSize, resSize))
    rhoW = max(abs(linalg.eig(W)[0]))
    W *= rho / rhoW
    W = np.float32(W)
    
    ae_weight, ae_bias = get_ae_weight()
    
    with tf.Graph().as_default(), tf.Session() as session:
        with tf.variable_scope("model", reuse=None):
            m_train = ESN(is_training=True, length=len(y_train[0]))
        with tf.variable_scope("model", reuse=True):
            m_test = ESN(is_training=False, length=len(y_test[0]))
            
        tf.initialize_all_variables().run()
        
        #log_a = Log('http://localhost:8120','modelA')
        # pastalog --serve 8120
        
        scale = cpu_load_std ** 2
        train_best = test_best = 0.0
        for i in range(FLAGS.epoch):
            if i < FLAGS.epoch/3:
                lr_decay = 1
            elif i < FLAGS.epoch*2/3:
                lr_decay = 0.1
            else:
                lr_decay = 0.01
            m_train.assign_lr(session, FLAGS.lr * lr_decay)
            train_loss, train_state = run_train_epoch(session, m_train, Win, W, X_train, 
                                                      y_train[:,100:,:], 
                                                      ae_weight, ae_bias, m_train.train_op)
            test_loss, _ = run_test_epoch(session, m_test, Win, W, 
                                          X_test, y_test, 
                                          ae_weight, ae_bias, tf.no_op(), train_state)
            if i == 0:
                train_best = train_loss
                test_best = test_loss
            if train_loss < train_best:
                train_best = train_loss
            if test_loss < test_best:
                test_best = test_loss
            print("epoch:%3d, learning rate %.5f, train_loss %.6f, test_loss %.6f" %
                    (i + 1, session.run(m_train.lr), train_loss*scale, test_loss*scale))
            #log_a.post("trainLoss", value=float(train_loss), step=i)
            #log_a.post("testLoss", value=float(test_loss), step=i)
            if i == FLAGS.epoch - 1:
                print("Best train, test loss %.6f %.6f" % (train_best*scale, test_best*scale))
            
    print("The input_dim is", FLAGS.input_dim, "The hidden_dim is", FLAGS.hidden_dim)
    print("The output_dim is", FLAGS.output_dim, "The batch_size is", FLAGS.batch_size)
    print("The ae_path is", FLAGS.ae_path)
    print("The data_path is", FLAGS.data_path)
    print("===============================================================================")    

if __name__ == "__main__":
    tf.app.run()
